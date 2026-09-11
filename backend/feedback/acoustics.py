"""Paraverbal measurement of one Turn's audio via Praat (ADR 0047).

The only module that imports parselmouth: everything else in the backend sees
plain numbers. Pure and synchronous -- no network, no database, no domain
vocabulary -- so it can be tested against synthetic waveforms alone.

What it produces is deliberately raw and additive: a duration, the silent
stretches inside the utterance, and two curves sampled at a fixed rate, one of
loudness and one of pitch. All of it concatenates across Turns without
weighting or interpolation, which is what lets the Session's statistics
describe the whole call rather than one utterance at a time (ADR 0051).
"""

from __future__ import annotations

import io
import warnings
import wave
from dataclasses import dataclass

import numpy as np
import parselmouth
from parselmouth.praat import call


class AcousticsError(Exception):
    """The audio could not be measured. Never fatal to a Session (ADR 0048)."""


# Praat's intensity analysis windows are derived from a pitch floor; this one
# spans typical adult speech of both sexes.
_PITCH_FLOOR_HZ = 75.0
# The other end of the same range (F-35), for the first of the two pitch passes
# below. Deliberately generous: the first pass only has to find the speaker's
# register, and a ceiling set too low there would clip a high voice before the
# second pass ever sees it.
_PITCH_CEILING_HZ = 600.0

# The pitch analysis grid. Praat's own default (0.75 / floor, about 10 ms at
# our floor), and emphatically *not* the 100 ms the loudness curve is sampled
# at: measured against synthetic contours of known range, that coarser grid
# understated a 3 Hz contour by 1.4 semitones and a 4 Hz one by 3.6, because
# speech intonation carries real movement around the syllable rate of 4 to 8 Hz
# and a 10 Hz sampler aliases it. The curve is thinned to the display grid
# afterwards; the statistics are computed on this one.
_PITCH_STEP_S = 0.01

# The second pass's floor and ceiling, as multiples of the first pass's own
# quartiles (De Looze & Hirst's two-pass procedure). A window that follows the
# speaker is what keeps a 116 Hz voice from being read at 483 Hz -- an octave
# error that a fixed window cannot rule out and that the percentile trim only
# just caught in the recordings this was checked against.
#
# The ceiling is 2.5 and not the 1.5 the procedure was first published with.
# The two figures are a real disagreement in the literature and not a typo:
# De Looze (2010) derived 1.5 * q3, and Hirst (2011) reports that on expressive
# speech that ceiling sits below the speaker's own rises and produces systematic
# octave *halving* -- the tracker, denied the true frequency, returns half of
# it. Since this application measures people arguing a case on the telephone,
# expressive rises are the normal material and the later figure is the one to
# follow. It costs a little of the protection against octave doubling at the top
# end, which is why the percentile trim in intonation.py stays where it is.
_PITCH_FLOOR_FACTOR = 0.75
_PITCH_CEILING_FACTOR = 2.5
# Below this many voiced frames the first pass has not established anything to
# narrow the window with, and the second pass is skipped.
_MIN_FRAMES_FOR_REFINEMENT = 10
# Below this, the analysis windows are longer than the audio itself.
_MIN_DURATION_S = 0.3
# Silence detection, in dB below the utterance's peak -- Praat's own default.
_SILENCE_THRESHOLD_DB = -25.0
_MIN_PAUSE_S = 0.25
_MIN_SOUNDING_S = 0.1
# Praat's intensity scale is referenced to 2e-5 Pa, and the samples reach it
# normalised to +/-1, so full-scale audio reads near 94 dB and speech well
# above 60. A recording that never reaches 40 dB held an RMS level a few
# thousandths of full scale: room tone, a muted microphone, or a dropped
# frame -- not an utterance.
_MIN_PEAK_DB = 40.0
# The loudness curve's resolution. Fixed in time rather than in points per
# Turn, so a long utterance contributes proportionally more of the Session's
# curve than a short one.
_SAMPLE_INTERVAL_MS = 100


@dataclass(frozen=True)
class Pause:
    """One silent stretch inside speech, located on a timeline by its start."""

    offset_ms: int
    duration_ms: int


@dataclass(frozen=True)
class TurnFacts:
    """What is kept of one user utterance once its audio is gone (ADR 0081).

    The subset of `TurnAcoustics` a later measurement needs, on the Session's
    timeline rather than the utterance's, and in a shape that survives a round
    trip through JSONB. The pitch curve is not part of it: no metric computed
    per segment reads it, and the Sprachmelodie is a reading over a whole call
    (F-35).

    Facts and not statistics, which is the whole of why storing them per
    utterance does not reopen ADR 0051: nothing here is a rate, a share or a
    figure anybody is shown.
    """

    speech_ms: int
    phonation_ms: int
    # False once any fragment of this utterance failed to measure. Carried
    # because a figure derived from an incomplete measurement is withheld
    # rather than estimated, and that decision cannot be made without knowing.
    complete: bool
    pauses: tuple[Pause, ...]
    loudness_db: tuple[float | None, ...]

    def as_json(self) -> dict:
        """The stored form. Keys are the field names, so the column reads as
        what it is without a schema beside it."""
        return {
            "speech_ms": self.speech_ms,
            "phonation_ms": self.phonation_ms,
            "complete": self.complete,
            "pauses": [
                {"offset_ms": p.offset_ms, "duration_ms": p.duration_ms}
                for p in self.pauses
            ],
            "loudness_db": list(self.loudness_db),
        }

    @classmethod
    def from_json(cls, stored: dict) -> "TurnFacts":
        """Read a stored row back. Tolerant of a missing key rather than
        raising: this is read in the worker, where a malformed row should cost
        one Session its segment figures and not the whole wrap-up."""
        return cls(
            speech_ms=int(stored.get("speech_ms") or 0),
            phonation_ms=int(stored.get("phonation_ms") or 0),
            complete=bool(stored.get("complete", True)),
            pauses=tuple(
                Pause(offset_ms=int(p["offset_ms"]), duration_ms=int(p["duration_ms"]))
                for p in stored.get("pauses") or []
            ),
            loudness_db=tuple(stored.get("loudness_db") or ()),
        )


@dataclass(frozen=True)
class TurnAcoustics:
    """Raw acoustic facts about one user utterance.

    Deliberately not domain metrics: the mapping onto MetricType rows, and every
    judgment about what counts as too fast or too quiet, lives in metrics.py.
    Offsets are relative to the start of this utterance; the caller rebases
    them onto the Session's timeline.
    """

    duration_ms: int
    phonation_ms: int          # speaking time, pauses excluded
    pauses: tuple[Pause, ...]
    # One sample per _SAMPLE_INTERVAL_MS; None while the speaker was silent.
    # Relative by nature: the browser's automatic gain control makes an
    # absolute level a statement about the user's headset (ADR 0047).
    loudness_db: tuple[float | None, ...]
    # Fundamental frequency on the same grid, None wherever the frame carried
    # no voicing -- which is most consonants, every pause and any breath, so a
    # dense curve is not to be expected and its gaps are not failures (F-35).
    #
    # Hertz, not semitones, and unconverted on purpose: this module produces
    # facts, and the conversion to a speaker-relative interval is a judgment
    # about what to compare against, which belongs in metrics.py.
    pitch_hz: tuple[float | None, ...]


def analyze(wav_bytes: bytes) -> TurnAcoustics:
    """Measure one Turn of recorded audio. Raises AcousticsError if it can't be."""
    samples, sample_rate = _decode_wav(wav_bytes)
    duration_s = len(samples) / sample_rate
    if duration_s < _MIN_DURATION_S:
        raise AcousticsError(f"Audio too short to analyze ({duration_s:.2f}s)")

    try:
        with warnings.catch_warnings():
            # Praat warns about things that are normal here (a quiet Turn has
            # little dynamic range); the useful failures come through PraatError.
            warnings.simplefilter("ignore", parselmouth.PraatWarning)
            sound = parselmouth.Sound(samples, sampling_frequency=sample_rate)
            intensity = sound.to_intensity(minimum_pitch=_PITCH_FLOOR_HZ)

            db = intensity.values[0]
            if db.size < 2 or db.max() < _MIN_PEAK_DB:
                raise AcousticsError("No audible speech in this Turn")

            # Which frames count as speech, for the curve. Praat applies the
            # same threshold to its own segmentation below, but arrives at it
            # separately, so the two can disagree at the margin of a frame.
            sounding = db > np.percentile(db, 99) + _SILENCE_THRESHOLD_DB
            pauses, phonation_s = _segment_silences(intensity, duration_s)

            return TurnAcoustics(
                duration_ms=round(duration_s * 1000),
                phonation_ms=round(phonation_s * 1000),
                pauses=pauses,
                loudness_db=_sample(np.where(sounding, db, np.nan), duration_s),
                pitch_hz=_pitch(sound),
            )
    except parselmouth.PraatError as e:
        raise AcousticsError(f"Praat analysis failed: {e}") from e


def _decode_wav(wav_bytes: bytes) -> tuple[np.ndarray, int]:
    """Decode the 16-bit PCM WAV the client sends into mono float samples.

    parselmouth.Sound reads paths and arrays, not bytes, so the alternative
    would be a temp file per Turn. The client always sends 16 kHz mono
    (frontend/src/utils/wav.ts); the channel fold is belt-and-braces.
    """
    try:
        with wave.open(io.BytesIO(wav_bytes)) as wav:
            if wav.getsampwidth() != 2:
                raise AcousticsError(f"Expected 16-bit PCM, got {wav.getsampwidth() * 8}-bit")
            channels, sample_rate = wav.getnchannels(), wav.getframerate()
            frames = wav.readframes(wav.getnframes())
    except wave.Error as e:
        raise AcousticsError(f"Not a readable WAV stream: {e}") from e

    samples = np.frombuffer(frames, dtype="<i2").astype(np.float64) / 32768.0
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    if samples.size == 0:
        raise AcousticsError("WAV stream contains no samples")
    return samples, sample_rate


def _segment_silences(
    intensity: parselmouth.Intensity, duration_s: float
) -> tuple[tuple[Pause, ...], float]:
    """Praat's silence segmentation, as pauses plus total speaking time.

    Pauses touching either end are dropped: the client's VAD trims around the
    utterance, so edge silence is its padding, not the user hesitating.
    """
    textgrid = call(
        intensity,
        "To TextGrid (silences)",
        _SILENCE_THRESHOLD_DB, _MIN_PAUSE_S, _MIN_SOUNDING_S,
        "silent", "sounding",
    )
    pauses: list[Pause] = []
    phonation_s = 0.0
    for interval in range(1, call(textgrid, "Get number of intervals", 1) + 1):
        start = call(textgrid, "Get start time of interval", 1, interval)
        end = call(textgrid, "Get end time of interval", 1, interval)
        if call(textgrid, "Get label of interval", 1, interval) == "sounding":
            phonation_s += end - start
        elif start > 0.0 and end < duration_s:
            pauses.append(
                Pause(offset_ms=round(start * 1000), duration_ms=round((end - start) * 1000))
            )
    return tuple(pauses), phonation_s


def _pitch(sound: parselmouth.Sound) -> tuple[float | None, ...]:
    """The fundamental frequency at 10 ms, measured twice (F-35).

    Two passes, which is the standard procedure for F0 and the reason this is
    not one line. A single pass has to be given a floor and a ceiling before
    anything is known about the voice, and a window wide enough for every
    speaker is wide enough to admit octave errors: a frame of creak read an
    octave down, a frame of noise read an octave up. In the first recordings
    this was checked against, a 116 Hz voice produced a frame at 483 Hz, four
    times its own median and hard against the ceiling.

    So the first pass only establishes the register, and the second measures
    inside a window built from that speaker's own quartiles (De Looze & Hirst).
    A doubled frame then falls outside the ceiling and is simply not returned,
    rather than being trimmed away afterwards and hoped about.

    Unvoiced frames come back as 0.0 and become None here: a zero would be a
    measured frequency of nothing, and averaging it in would pull every figure
    derived from this curve towards a value nobody produced.

    Returns an empty tuple when the tracker finds nothing, which a Turn of pure
    noise or whispering legitimately produces. The caller treats that as a
    missing curve, not as an error -- the rest of the measurement is still good.
    """
    first = _track(sound, _PITCH_FLOOR_HZ, _PITCH_CEILING_HZ)
    voiced = first[first > 0]
    if voiced.size < _MIN_FRAMES_FOR_REFINEMENT:
        return _as_curve(first)

    # Quartiles rather than the extremes: the extremes are exactly what may be
    # wrong at this point.
    low, high = np.percentile(voiced, [25, 75])
    refined = _track(
        sound,
        max(_PITCH_FLOOR_HZ, float(low) * _PITCH_FLOOR_FACTOR),
        float(high) * _PITCH_CEILING_FACTOR,
    )
    # A narrowed window that finds nothing is a sign the first pass was noise,
    # not that the speaker fell silent; keep the wider reading in that case.
    return _as_curve(refined if (refined > 0).sum() >= _MIN_FRAMES_FOR_REFINEMENT else first)


def _track(sound: parselmouth.Sound, floor_hz: float, ceiling_hz: float) -> np.ndarray:
    """One pass of Praat's autocorrelation tracker, 0.0 where unvoiced."""
    pitch = sound.to_pitch(
        time_step=_PITCH_STEP_S, pitch_floor=floor_hz, pitch_ceiling=ceiling_hz
    )
    return np.asarray(pitch.selected_array["frequency"], dtype=np.float64)


def _as_curve(frequencies: np.ndarray) -> tuple[float | None, ...]:
    """Praat's array as the curve the rest of the backend reads."""
    if frequencies.size == 0:
        return ()
    return tuple(
        None if value <= 0 else round(float(value), 1) for value in frequencies
    )


def _sample(values: np.ndarray, duration_s: float) -> tuple[float | None, ...]:
    """Thin a frame-rate curve to one point per _SAMPLE_INTERVAL_MS, NaN -> None."""
    points = max(2, round(duration_s * 1000 / _SAMPLE_INTERVAL_MS))
    if values.size > points:
        values = values[np.linspace(0, values.size - 1, points).astype(int)]
    return tuple(None if np.isnan(v) else round(float(v), 1) for v in values)
