"""Paraverbal measurement of one Turn's audio via Praat (ADR 0045).

The only module that imports parselmouth: everything else in the backend sees
plain numbers. Pure and synchronous -- no network, no database, no domain
vocabulary -- so it can be tested against synthetic waveforms alone.

What it produces is deliberately raw and additive: a duration, the silent
stretches inside the utterance, and a loudness curve sampled at a fixed rate.
All three concatenate across Turns without weighting or interpolation, which
is what lets the Session's statistics describe the whole call rather than one
utterance at a time (ADR 0049).
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
    """The audio could not be measured. Never fatal to a Session (ADR 0046)."""


# Praat's intensity analysis windows are derived from a pitch floor; this one
# spans typical adult speech of both sexes.
_PITCH_FLOOR_HZ = 75.0
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
class TurnAcoustics:
    """Raw acoustic facts about one user utterance.

    Deliberately not domain metrics: the mapping onto MetrikTyp rows, and every
    judgment about what counts as too fast or too quiet, lives in metrics.py.
    Offsets are relative to the start of this utterance; the caller rebases
    them onto the Session's timeline.
    """

    duration_ms: int
    phonation_ms: int          # speaking time, pauses excluded
    pauses: tuple[Pause, ...]
    # One sample per _SAMPLE_INTERVAL_MS; None while the speaker was silent.
    # Relative by nature: the browser's automatic gain control makes an
    # absolute level a statement about the user's headset (ADR 0045).
    loudness_db: tuple[float | None, ...]


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


def _sample(values: np.ndarray, duration_s: float) -> tuple[float | None, ...]:
    """Thin a frame-rate curve to one point per _SAMPLE_INTERVAL_MS, NaN -> None."""
    points = max(2, round(duration_s * 1000 / _SAMPLE_INTERVAL_MS))
    if values.size > points:
        values = values[np.linspace(0, values.size - 1, points).astype(int)]
    return tuple(None if np.isnan(v) else round(float(v), 1) for v in values)
