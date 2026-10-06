"""Per-account caps on model work (ADR 0109). Counted in-process: the backend
runs one gunicorn worker, and a second would multiply every cap."""
from __future__ import annotations

import threading
import time
from collections import Counter, deque
from collections.abc import Callable

from fastapi import HTTPException, status

# Two: a reload can open the next socket before the last one is noticed gone.
MAX_OPEN_CALLS = 2
# Checked between turns, so a turn in flight can overrun it.
MAX_CALL_S = 30 * 60
# 16 kHz 16-bit mono: a bit over two minutes of speech.
MAX_TURN_AUDIO_BYTES = 4 * 1024 * 1024
# Just above one turn, so the turn check answers first; it also bounds the
# unauthenticated handshake frame (uvicorn's default is 16 MB).
WS_MAX_FRAME_BYTES = MAX_TURN_AUDIO_BYTES + 64 * 1024

_HOUR_S = 60 * 60


class CallSlots:
    def __init__(self, per_subject: int) -> None:
        self._per_subject = per_subject
        self._open: Counter[str] = Counter()
        self._lock = threading.Lock()

    def claim(self, subject: str) -> bool:
        with self._lock:
            if self._open[subject] >= self._per_subject:
                return False
            self._open[subject] += 1
            return True

    def release(self, subject: str) -> None:
        with self._lock:
            self._open[subject] -= 1
            if self._open[subject] <= 0:
                del self._open[subject]


class RateLimit:
    def __init__(
        self, limit: int, window_s: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._limit = limit
        self._window_s = window_s
        self._clock = clock
        self._uses: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, subject: str) -> bool:
        now = self._clock()
        with self._lock:
            uses = self._uses.setdefault(subject, deque())
            while uses and uses[0] <= now - self._window_s:
                uses.popleft()
            if len(uses) >= self._limit:
                return False
            uses.append(now)
            return True


def enforce(limit: RateLimit, subject: str) -> None:
    if not limit.allow(subject):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Diese Funktion wurde in der letzten Stunde zu oft genutzt. "
            "Bitte später noch einmal versuchen.",
        )


# Every request counts: reading the PDFs is work before the model is asked.
DOCUMENT_SUMMARIES_PER_HOUR = 20
# Reverses and follow-ups together; returning a stored one is free.
SCENARIO_DRAFTS_PER_HOUR = 20


def fresh() -> tuple[CallSlots, RateLimit, RateLimit]:
    return (
        CallSlots(MAX_OPEN_CALLS),
        RateLimit(DOCUMENT_SUMMARIES_PER_HOUR, _HOUR_S),
        RateLimit(SCENARIO_DRAFTS_PER_HOUR, _HOUR_S),
    )


# Read as `limits.X` at the call site, so tests can swap in fresh counters.
OPEN_CALLS, DOCUMENT_SUMMARIES, SCENARIO_DRAFTS = fresh()
