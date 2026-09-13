"""Hesitation sounds ("äh", "ähm", "hm") read off the pitch contour (F-51).

Whisper drops them, so the transcript cannot count them. What they leave in the
audio is a held, voiced sound whose pitch barely moves, where running speech
moves several times a second. An estimate: a drawn-out "jaaa" has the same shape.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.feedback.intonation import STEP_MS, semitones

# Provisional until checked against recordings. A filled pause usually runs 200
# to 600 ms, and a quarter second of flat voicing is rare in running speech.
MIN_HOLD_MS = 250
# How far the pitch may wander within a hold, as a total span in semitones.
# Wide enough for tracker jitter (~0.3 st), narrow enough to exclude intonation.
MAX_SPAN_ST = 2.0


@dataclass(frozen=True)
class Hold:
    """One held stretch, located within its utterance."""

    start_ms: int
    duration_ms: int


def holds(utterance: tuple[float | None, ...]) -> list[Hold]:
    """The held, flat, voiced stretches in one utterance's 10 ms contour."""
    min_frames = MIN_HOLD_MS // STEP_MS
    found: list[Hold] = []
    start = 0
    while start < len(utterance):
        end = _flat_end(utterance, start)
        if end - start >= min_frames:
            found.append(Hold(start * STEP_MS, (end - start) * STEP_MS))
            start = end
        else:
            start += 1
    return found


def _flat_end(utterance: tuple[float | None, ...], start: int) -> int:
    """Where the flat voiced stretch beginning at `start` stops, exclusive.

    An unvoiced frame ends it: a hesitation sound is voiced throughout.
    """
    reference = utterance[start]
    if reference is None:
        return start
    low = high = 0.0
    end = start + 1
    while end < len(utterance):
        hz = utterance[end]
        if hz is None:
            break
        interval = semitones(hz, reference)
        low, high = min(low, interval), max(high, interval)
        if high - low > MAX_SPAN_ST:
            break
        end += 1
    return end
