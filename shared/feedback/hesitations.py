"""Hesitation sounds read off the pitch contour (F-51, ADR 0084). An estimate:
a drawn-out "jaaa" has the same shape."""

from __future__ import annotations

from dataclasses import dataclass

from shared.feedback.intonation import STEP_MS, semitones

# Both provisional until checked against recordings.
MIN_HOLD_MS = 250
# Total pitch span within a hold: above tracker jitter (~0.3 st), below intonation.
MAX_SPAN_ST = 2.0


@dataclass(frozen=True)
class Hold:
    start_ms: int
    duration_ms: int


def holds(utterance: tuple[float | None, ...]) -> list[Hold]:
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
    # An unvoiced frame ends it: a hesitation sound is voiced throughout.
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
