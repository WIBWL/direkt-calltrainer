"""Praat on synthetic tones, the one place real Praat runs (F-35, F-37, F-51, ADR 0047)."""
import io
import math
import wave

import numpy as np
import pytest

from shared.feedback import intonation
from shared.feedback.acoustics import AcousticsError, analyze
from shared.feedback.calls import Conversation
from shared.feedback.metrics import measure

SAMPLE_RATE = 16_000  # what the client sends (frontend/src/utils/wav.ts)


def _wav(samples: np.ndarray, sample_rate: int = SAMPLE_RATE) -> bytes:
    """The samples as the 16-bit mono PCM WAV `analyze` expects."""
    buffer = io.BytesIO()
    # pylint: disable=no-member  # wave.open("wb") returns Wave_write; pylint infers Wave_read
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(sample_rate)
        out.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())
    return buffer.getvalue()


def _tone(frequency_hz: float, seconds: float, amplitude: float = 0.5) -> np.ndarray:
    """A plain sine. Praat's autocorrelation tracker reads these exactly, which
    is what makes the expected value a number rather than a range."""
    t = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    return amplitude * np.sin(2 * np.pi * frequency_hz * t)


def _fm_tone(base: float, depth_st: float, rate_hz: float, seconds: float) -> np.ndarray:
    """A tone whose pitch swings sinusoidally, +/- `depth_st` semitones around
    `base`. The peak-to-peak range is therefore twice `depth_st`."""
    t = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    frequency = base * 2 ** (depth_st / 12 * np.sin(2 * np.pi * rate_hz * t))
    return 0.5 * np.sin(2 * np.pi * np.cumsum(frequency) / SAMPLE_RATE)


def _voiced(measured) -> list[float]:
    return [v for v in measured.pitch_hz if v is not None]


def test_a_steady_tone_is_measured_at_its_own_frequency() -> None:
    measured = analyze(_wav(_tone(120, 2.0)))

    voiced = _voiced(measured)
    assert len(voiced) > 10, "a two-second tone should yield a dense curve"
    assert all(abs(hz - 120) < 5 for hz in voiced), voiced[:10]


def test_the_pitch_curve_is_measured_on_the_fine_grid() -> None:
    measured = analyze(_wav(_tone(150, 2.0)))

    assert len(measured.loudness_db) == 20              # 2 s at 100 ms
    assert len(measured.pitch_hz) > 150                 # 2 s at 10 ms, minus edges
    assert len(intonation.thin(measured.pitch_hz, 100)) == pytest.approx(20, abs=2)


def test_the_fine_grid_recovers_a_contour_the_coarse_one_lost() -> None:
    swinging = _fm_tone(150, depth_st=8.0, rate_hz=3.0, seconds=6.0)

    measured = analyze(_wav(swinging))
    fine = intonation.profile(measured.pitch_hz, (measured.pitch_hz,)).range_st
    coarse = intonation.profile(
        tuple(intonation.thin(measured.pitch_hz, 100)), (measured.pitch_hz,)
    ).range_st

    assert fine is not None and coarse is not None
    assert fine > coarse + 1.0


def test_silence_is_not_reported_as_a_frequency() -> None:
    half = _tone(140, 1.0)
    measured = analyze(_wav(np.concatenate([half, np.zeros(SAMPLE_RATE)])))

    assert None in measured.pitch_hz
    assert all(hz > 0 for hz in _voiced(measured))


def test_a_step_in_pitch_is_measured_as_the_interval_it_is() -> None:
    stepped = np.concatenate([_tone(120, 1.5), _tone(180, 1.5)])

    measured = analyze(_wav(stepped))
    call = Conversation(user_text="egal", pitch_hz=measured.pitch_hz)
    value = next(m.value for m in measure(call) if m.key == "intonation")

    assert value == pytest.approx(12 * math.log2(180 / 120), abs=1.0)


def test_the_same_interval_from_a_higher_voice_yields_the_same_figure() -> None:
    low = analyze(_wav(np.concatenate([_tone(110, 1.5), _tone(165, 1.5)])))
    high = analyze(_wav(np.concatenate([_tone(220, 1.5), _tone(330, 1.5)])))

    def span(measured) -> float:
        call = Conversation(user_text="egal", pitch_hz=measured.pitch_hz)
        return next(m.value for m in measure(call) if m.key == "intonation")

    assert span(low) == pytest.approx(span(high), abs=0.7)


def test_a_flat_tone_has_almost_no_range() -> None:
    measured = analyze(_wav(_tone(130, 3.0)))

    call = Conversation(user_text="egal", pitch_hz=measured.pitch_hz)
    value = next(m.value for m in measure(call) if m.key == "intonation")

    assert value < 1.0


def _silence(seconds: float) -> np.ndarray:
    return np.zeros(int(seconds * SAMPLE_RATE))


def test_the_sound_is_found_inside_the_vads_padding() -> None:
    measured = analyze(_wav(np.concatenate([_silence(0.8), _tone(150, 1.0), _silence(1.0)])))

    assert measured.voice_start_ms == pytest.approx(800, abs=60)
    assert measured.voice_end_ms == pytest.approx(1_800, abs=60)


def test_the_span_between_first_and_last_sound_is_speech_plus_pauses() -> None:
    measured = analyze(_wav(np.concatenate(
        [_silence(0.8), _tone(150, 0.8), _silence(0.5), _tone(150, 0.8), _silence(1.0)]
    )))

    span = measured.voice_end_ms - measured.voice_start_ms
    pauses = sum(pause.duration_ms for pause in measured.pauses)

    assert len(measured.pauses) == 1
    assert measured.phonation_ms + pauses == pytest.approx(span, abs=2)


def test_audio_too_short_to_analyse_is_refused_rather_than_guessed() -> None:
    with pytest.raises(AcousticsError):
        analyze(_wav(_tone(120, 0.1)))


def test_a_silent_recording_is_refused() -> None:
    with pytest.raises(AcousticsError):
        analyze(_wav(np.zeros(SAMPLE_RATE * 2)))
