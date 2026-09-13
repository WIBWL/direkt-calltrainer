"""Paraverbal measurement against synthetic audio (F-35, F-37, F-51, ADR 0047).

The one place the real Praat analysis runs in the suite. Everything else hands
`metrics.py` the numbers `analyze()` would have produced, which keeps those
tests fast and free of a C extension — but leaves the measurement itself
unproven, and the pitch curve of F-35 is exactly the kind of thing that is
either right or quietly a factor of two out.

Synthetic waveforms, so the answer is known in advance: a 120 Hz tone is 120 Hz,
and a tone that steps to 180 Hz spans 12·log2(180/120) ≈ 7.02 semitones. No
recording, no fixture, no network.

What these tests do not check is whether Praat tracks *speech* well. That is a
property of Praat, established elsewhere and not this suite's to re-derive.
"""
import io
import math
import wave

import numpy as np
import pytest

from backend.feedback import intonation
from backend.feedback.acoustics import AcousticsError, analyze
from backend.feedback.calls import Conversation
from backend.feedback.metrics import measure

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
    """The floor under everything else here: if this is off, every figure
    derived from the curve is off by the same factor."""
    measured = analyze(_wav(_tone(120, 2.0)))

    voiced = _voiced(measured)
    assert len(voiced) > 10, "a two-second tone should yield a dense curve"
    assert all(abs(hz - 120) < 5 for hz in voiced), voiced[:10]


def test_the_pitch_curve_is_measured_on_the_fine_grid() -> None:
    """Ten milliseconds, not the hundred the loudness curve is sampled at.

    The two grids were the same once, and that was a defect rather than a
    feature: measured against synthetic contours of known range, a 100 ms
    sampler understated a 3 Hz contour by 1.4 semitones and a 4 Hz one by 3.6,
    because speech intonation carries real movement around the syllable rate.
    Nothing plots the two curves against each other, so nothing was lost by
    separating them, and the stored curve is thinned back down for display.
    """
    measured = analyze(_wav(_tone(150, 2.0)))

    assert len(measured.loudness_db) == 20              # 2 s at 100 ms
    assert len(measured.pitch_hz) > 150                 # 2 s at 10 ms, minus edges
    assert len(intonation.thin(measured.pitch_hz, 100)) == pytest.approx(20, abs=2)


def test_the_fine_grid_recovers_a_contour_the_coarse_one_lost() -> None:
    """The defect this change was made for, as a number. A contour that swings
    16 semitones at 3 Hz reads as 14.4 on a 100 ms grid and as 15.8 on the real
    one -- and the faster the contour, the more the coarse grid loses."""
    swinging = _fm_tone(150, depth_st=8.0, rate_hz=3.0, seconds=6.0)

    measured = analyze(_wav(swinging))
    fine = intonation.profile(measured.pitch_hz, (measured.pitch_hz,)).range_st
    coarse = intonation.profile(
        tuple(intonation.thin(measured.pitch_hz, 100)), (measured.pitch_hz,)
    ).range_st

    assert fine is not None and coarse is not None
    assert fine > coarse + 1.0


def test_silence_is_not_reported_as_a_frequency() -> None:
    """Praat returns 0.0 for an unvoiced frame. Kept as 0 it would be a
    measured frequency of nothing and would drag every derived figure down."""
    half = _tone(140, 1.0)
    measured = analyze(_wav(np.concatenate([half, np.zeros(SAMPLE_RATE)])))

    assert None in measured.pitch_hz
    assert all(hz > 0 for hz in _voiced(measured))


def test_a_step_in_pitch_is_measured_as_the_interval_it_is() -> None:
    """120 Hz to 180 Hz is a fifth, seven semitones, whoever sings it. The
    metric reports semitones for exactly this reason: the same interval from a
    lower or higher voice has to yield the same number (F-35)."""
    stepped = np.concatenate([_tone(120, 1.5), _tone(180, 1.5)])

    measured = analyze(_wav(stepped))
    call = Conversation(user_text="egal", pitch_hz=measured.pitch_hz)
    value = next(m.value for m in measure(call) if m.key == "intonation")

    assert value == pytest.approx(12 * math.log2(180 / 120), abs=1.0)


def test_the_same_interval_from_a_higher_voice_yields_the_same_figure() -> None:
    """The property that makes the unit worth its conversion. In Hertz these
    two calls would differ by 50%, and the figure would be describing the
    speaker's voice rather than what they did with it."""
    low = analyze(_wav(np.concatenate([_tone(110, 1.5), _tone(165, 1.5)])))
    high = analyze(_wav(np.concatenate([_tone(220, 1.5), _tone(330, 1.5)])))

    def span(measured) -> float:
        call = Conversation(user_text="egal", pitch_hz=measured.pitch_hz)
        return next(m.value for m in measure(call) if m.key == "intonation")

    assert span(low) == pytest.approx(span(high), abs=0.7)


def test_a_flat_tone_has_almost_no_range() -> None:
    """A monotone delivery must not come out looking varied. No judgement is
    attached to the number either way (ADR 0051) — this only pins that the
    measurement follows the signal."""
    measured = analyze(_wav(_tone(130, 3.0)))

    call = Conversation(user_text="egal", pitch_hz=measured.pitch_hz)
    value = next(m.value for m in measure(call) if m.key == "intonation")

    assert value < 1.0


def test_audio_too_short_to_analyse_is_refused_rather_than_guessed() -> None:
    """`analyze` raising is how a Turn ends up unmeasured, which the live path
    treats as normal (ADR 0048). Returning a made-up figure would be worse."""
    with pytest.raises(AcousticsError):
        analyze(_wav(_tone(120, 0.1)))


def test_a_silent_recording_is_refused() -> None:
    """Room tone or a muted microphone: there is nothing here to measure, and
    the metrics must not receive a curve of nothing."""
    with pytest.raises(AcousticsError):
        analyze(_wav(np.zeros(SAMPLE_RATE * 2)))
