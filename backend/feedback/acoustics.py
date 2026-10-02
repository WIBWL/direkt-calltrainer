"""Paraverbal measurement of one Turn's audio via Praat (ADR 0047).

The only module that imports parselmouth; pure, so testable on synthetic tones.
Output is raw and additive, so it concatenates across Turns (ADR 0051).
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

# The pitch analysis grid: Praat's default, and *not* the loudness curve's
# 100 ms, which aliases intonation at the syllable rate (ADR 0077). The curve is
# thinned for display afterwards; the statistics are computed on this grid.
_PITCH_STEP_S = 0.01

# Second-pass window as multiples of the first pass's quartiles (De Looze &
# Hirst). The ceiling is 2.5 (Hirst 2011), not De Looze's 1.5, which sits below
# expressive rises and causes octave *halving* -- not a typo (ADR 0077). The
# percentile trim in intonation.py still guards the top end.
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
    The subset of `TurnAcoustics` segment metrics need, on the Session's
    timeline; facts, never statistics or anything shown (ADR 0051).
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
    """Raw acoustic facts about one user utterance; metrics.py maps them onto
    MetricType rows. Offsets are relative to this utterance; the caller rebases
    them onto the Session's timeline.
    """

    duration_ms: int
    phonation_ms: int          # speaking time, pauses excluded
    pauses: tuple[Pause, ...]
    # One sample per _SAMPLE_INTERVAL_MS; None while the speaker was silent.
    # Relative by nature: the browser's automatic gain control makes an
    # absolute level a statement about the user's headset (ADR 0047).
    loudness_db: tuple[float | None, ...]
    # F0 on the 10 ms pitch grid, not the loudness grid (ADR 0077). None where
    # unvoiced (consonants, pauses), so gaps are expected, not failures (F-35).
    # Hertz on purpose: converting to semitones is metrics.py's judgment.
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
    """Decode the client's 16-bit PCM WAV into mono float samples (parselmouth
    takes arrays, not bytes). The client sends 16 kHz mono
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
    """The fundamental frequency at 10 ms, in two passes (F-35): the first finds
    the register, the second measures inside the speaker's own quartile window
    (De Looze & Hirst) to keep octave errors out. Unvoiced frames are None,
    never 0.0; an empty result is a missing curve, not an error.
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
    # A narrowed window that finds *almost* nothing is a sign the first pass was
    # noise, not that the speaker fell silent; keep the wider reading there.
    # Known gap: a low excursion below the (tighter) new floor is lost
    # unnoticed; on speech-like contours that is a handful of frames.
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
    """Thin a frame-rate curve to roughly one point per _SAMPLE_INTERVAL_MS,
    NaN -> None. The real spacing is duration / round(duration / 100 ms);
    readers assume exactly 100 ms (`frontend/src/utils/loudness.ts`,
    `metrics._SMOOTH_POINTS`), accurate within 2.5 % from two seconds up.
    """
    points = max(2, round(duration_s * 1000 / _SAMPLE_INTERVAL_MS))
    if values.size > points:
        values = values[np.linspace(0, values.size - 1, points).astype(int)]
    return tuple(None if np.isnan(v) else round(float(v), 1) for v in values)
