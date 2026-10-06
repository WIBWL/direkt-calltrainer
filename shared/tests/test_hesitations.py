"""Hesitation sounds from synthetic contours (F-51, ADR 0084)."""

import math

from shared.feedback.hesitations import Hold, holds
from shared.feedback.metrics import measure
from shared.feedback.calls import conversation
from shared.turn import Turn

_VOICE_HZ = 120.0


def _flat(ms: int, hz: float = _VOICE_HZ) -> list[float | None]:
    return [hz] * (ms // 10)


def _moving(ms: int) -> list[float | None]:
    """Running speech: ±3 semitones at a syllable rate of 4.5 Hz."""
    return [_VOICE_HZ * 2 ** (3 * math.sin(2 * math.pi * 4.5 * i / 100) / 12)
            for i in range(ms // 10)]


def test_a_held_flat_sound_is_one_hesitation() -> None:
    found = holds(tuple(_moving(500) + _flat(300) + _moving(500)))

    assert len(found) == 1
    assert 290 <= found[0].duration_ms <= 330


def test_running_speech_has_none() -> None:
    assert not holds(tuple(_moving(3000)))


def test_a_short_flat_stretch_is_not_long_enough() -> None:
    assert not holds(tuple(_moving(500) + _flat(150) + _moving(500)))


def test_tracker_jitter_does_not_break_a_hold() -> None:
    jittered = [_VOICE_HZ * (1.02 if i % 2 else 0.98) for i in range(30)]

    assert holds(tuple(jittered)) == [Hold(0, 300)]


def test_an_unvoiced_frame_ends_a_hold() -> None:
    assert not holds(tuple(_flat(200) + [None] + _flat(200)))


def test_the_metric_is_absent_when_the_acoustics_failed() -> None:
    turns = [Turn(seq=1, user_text="Also.", user_acoustics_complete=False,
                  pitch_hz=_flat(400))]

    assert "hesitations" not in {m.key for m in measure(conversation(turns, "de"))}
