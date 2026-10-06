"""Paraverbal measurement of one Turn's audio, the only parselmouth importer
(ADR 0047). Output is raw and additive, so it concatenates across Turns."""

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


_PITCH_FLOOR_HZ = 75.0
# Generous: the first pass only finds the register; too low would clip a high voice.
_PITCH_CEILING_HZ = 600.0

# Not the loudness curve's 100 ms, which aliases intonation (ADR 0077).
_PITCH_STEP_S = 0.01

# Second-pass window as multiples of the first pass's quartiles. 2.5 (Hirst
# 2011), not De Looze's 1.5, which causes octave halving on expressive rises.
_PITCH_FLOOR_FACTOR = 0.75
_PITCH_CEILING_FACTOR = 2.5
_MIN_FRAMES_FOR_REFINEMENT = 10
_MIN_DURATION_S = 0.3
# Praat's default, in dB below the utterance's peak.
_SILENCE_THRESHOLD_DB = -25.0
_MIN_PAUSE_S = 0.25
_MIN_SOUNDING_S = 0.1
# Full scale reads near 94 dB and speech above 60; a peak under 40 dB is room
# tone or a muted microphone, not an utterance.
_MIN_PEAK_DB = 40.0
_SAMPLE_INTERVAL_MS = 100


@dataclass(frozen=True)
class Pause:
    offset_ms: int
    duration_ms: int


@dataclass(frozen=True)
class TurnFacts:
    """What is kept of one user utterance once the audio is gone (ADR 0081):
    facts, never statistics."""

    speech_ms: int
    phonation_ms: int
    # False once any fragment failed to measure.
    complete: bool
    pauses: tuple[Pause, ...]
    loudness_db: tuple[float | None, ...]

    def as_json(self) -> dict:
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
        """Tolerant of missing keys: a malformed row should cost one Session its
        segment figures, not the wrap-up."""
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
    """Offsets are relative to this utterance; the caller rebases them."""

    duration_ms: int
    phonation_ms: int
    # First sound and last, excluding the VAD padding around them (ADR 0114).
    voice_start_ms: int
    voice_end_ms: int
    pauses: tuple[Pause, ...]
    # None while silent. A range, not a level: browser AGC makes levels describe the headset.
    loudness_db: tuple[float | None, ...]
    # 10 ms grid; None where unvoiced. Hertz: semitones are metrics.py's call.
    pitch_hz: tuple[float | None, ...]


def analyze(wav_bytes: bytes) -> TurnAcoustics:
    samples, sample_rate = _decode_wav(wav_bytes)
    duration_s = len(samples) / sample_rate
    if duration_s < _MIN_DURATION_S:
        raise AcousticsError(f"Audio too short to analyze ({duration_s:.2f}s)")

    try:
        with warnings.catch_warnings():
            # Praat warns about normal things here; real failures raise PraatError.
            warnings.simplefilter("ignore", parselmouth.PraatWarning)
            sound = parselmouth.Sound(samples, sampling_frequency=sample_rate)
            intensity = sound.to_intensity(minimum_pitch=_PITCH_FLOOR_HZ)

            db = intensity.values[0]
            if db.size < 2 or db.max() < _MIN_PEAK_DB:
                raise AcousticsError("No audible speech in this Turn")

            # Thresholded separately from Praat's segmentation; they can differ by a frame.
            sounding = db > np.percentile(db, 99) + _SILENCE_THRESHOLD_DB
            voice = _segment_silences(intensity, duration_s)

            return TurnAcoustics(
                duration_ms=round(duration_s * 1000),
                phonation_ms=round(voice.phonation_s * 1000),
                voice_start_ms=round(voice.start_s * 1000),
                voice_end_ms=round(voice.end_s * 1000),
                pauses=voice.pauses,
                loudness_db=_sample(np.where(sounding, db, np.nan), duration_s),
                pitch_hz=_pitch(sound),
            )
    except parselmouth.PraatError as e:
        raise AcousticsError(f"Praat analysis failed: {e}") from e


def _decode_wav(wav_bytes: bytes) -> tuple[np.ndarray, int]:
    """16-bit PCM WAV to mono float samples."""
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


@dataclass(frozen=True)
class _Voice:
    pauses: tuple[Pause, ...]
    phonation_s: float
    # Everything between is phonation or a pause, so the span is their sum.
    start_s: float
    end_s: float


def _segment_silences(intensity: parselmouth.Intensity, duration_s: float) -> _Voice:
    """Pauses touching either end are dropped: edge silence is VAD padding."""
    textgrid = call(
        intensity,
        "To TextGrid (silences)",
        _SILENCE_THRESHOLD_DB, _MIN_PAUSE_S, _MIN_SOUNDING_S,
        "silent", "sounding",
    )
    pauses: list[Pause] = []
    phonation_s = 0.0
    sounding: list[tuple[float, float]] = []
    for interval in range(1, call(textgrid, "Get number of intervals", 1) + 1):
        start = call(textgrid, "Get start time of interval", 1, interval)
        end = call(textgrid, "Get end time of interval", 1, interval)
        if call(textgrid, "Get label of interval", 1, interval) == "sounding":
            phonation_s += end - start
            sounding.append((start, end))
        elif start > 0.0 and end < duration_s:
            pauses.append(
                Pause(offset_ms=round(start * 1000), duration_ms=round((end - start) * 1000))
            )
    # Ruled out by the peak check; the whole recording is the fallback.
    first, last = (sounding[0][0], sounding[-1][1]) if sounding else (0.0, duration_s)
    return _Voice(tuple(pauses), phonation_s, first, last)


def _pitch(sound: parselmouth.Sound) -> tuple[float | None, ...]:
    """F0 at 10 ms in two passes: the first finds the register, the second
    measures inside the speaker's quartile window to keep octave errors out.
    Unvoiced frames are None, never 0.0."""
    first = _track(sound, _PITCH_FLOOR_HZ, _PITCH_CEILING_HZ)
    voiced = first[first > 0]
    if voiced.size < _MIN_FRAMES_FOR_REFINEMENT:
        return _as_curve(first)

    # Quartiles: the extremes are what may be wrong at this point.
    low, high = np.percentile(voiced, [25, 75])
    refined = _track(
        sound,
        max(_PITCH_FLOOR_HZ, float(low) * _PITCH_FLOOR_FACTOR),
        float(high) * _PITCH_CEILING_FACTOR,
    )
    # A narrowed window finding almost nothing means the first pass was noise.
    return _as_curve(refined if (refined > 0).sum() >= _MIN_FRAMES_FOR_REFINEMENT else first)


def _track(sound: parselmouth.Sound, floor_hz: float, ceiling_hz: float) -> np.ndarray:
    pitch = sound.to_pitch(
        time_step=_PITCH_STEP_S, pitch_floor=floor_hz, pitch_ceiling=ceiling_hz
    )
    return np.asarray(pitch.selected_array["frequency"], dtype=np.float64)


def _as_curve(frequencies: np.ndarray) -> tuple[float | None, ...]:
    if frequencies.size == 0:
        return ()
    return tuple(
        None if value <= 0 else round(float(value), 1) for value in frequencies
    )


def _sample(values: np.ndarray, duration_s: float) -> tuple[float | None, ...]:
    """Thin to about one point per 100 ms, NaN -> None. Readers assume exactly
    100 ms, accurate within 2.5 % from two seconds up."""
    points = max(2, round(duration_s * 1000 / _SAMPLE_INTERVAL_MS))
    if values.size > points:
        values = values[np.linspace(0, values.size - 1, points).astype(int)]
    return tuple(None if np.isnan(v) else round(float(v), 1) for v in values)
