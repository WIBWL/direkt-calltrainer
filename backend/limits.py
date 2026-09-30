"""How much model work one account may cause (ADR 0109).

Every route that reaches the LLM, Whisper or KugelAudio needs a login with the
`calltrainer-user` role; these caps bound what one such account -- or one stolen
token -- can spend. Counted per `sub` and in-process: the backend runs one
worker process (the Dockerfile's gunicorn command), so a dict is the whole
picture. A second process would multiply every cap by the process count.
"""
from __future__ import annotations

import threading
import time
from collections import Counter, deque
from collections.abc import Callable

from fastapi import HTTPException, status

# Calls one account may have open at once. Two, not one: a call's slot is freed
# only when its socket is gone, and a reload mid-call can open the next socket
# before the server has noticed the last one drop.
MAX_OPEN_CALLS = 2
# The longest a call runs. Checked between turns: the call ends at the first
# moment past this that nobody is speaking, so a turn in flight can overrun it.
MAX_CALL_S = 30 * 60
# One recorded turn: 16 kHz 16-bit mono WAV (useMicrophoneVAD.ts), 32 kB/s, so
# a bit over two minutes of speech -- far past any turn in a phone call, and
# the most one turn sends to Whisper.
MAX_TURN_AUDIO_BYTES = 4 * 1024 * 1024
# The socket's own frame ceiling (backend/gunicorn_worker.py), just above one
# turn, so the turn check above answers first and the handshake frame an
# unauthenticated client sends is bounded too. uvicorn's default is 16 MB.
WS_MAX_FRAME_BYTES = MAX_TURN_AUDIO_BYTES + 64 * 1024

_HOUR_S = 60 * 60


class CallSlots:
    """The calls each account has open, refused past `per_subject`."""

    def __init__(self, per_subject: int) -> None:
        self._per_subject = per_subject
        self._open: Counter[str] = Counter()
        self._lock = threading.Lock()

    def claim(self, subject: str) -> bool:
        """Take a slot for `subject`; False when all of theirs are taken."""
        with self._lock:
            if self._open[subject] >= self._per_subject:
                return False
            self._open[subject] += 1
            return True

    def release(self, subject: str) -> None:
        """Give one of `subject`'s slots back."""
        with self._lock:
            self._open[subject] -= 1
            if self._open[subject] <= 0:
                del self._open[subject]


class RateLimit:
    """At most `limit` uses per account in any `window_s` seconds."""

    def __init__(
        self, limit: int, window_s: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._limit = limit
        self._window_s = window_s
        self._clock = clock
        self._uses: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, subject: str) -> bool:
        """Count one use for `subject`, or answer False without counting it."""
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
    """Raise 429 when `subject` has used up `limit`."""
    if not limit.allow(subject):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Diese Funktion wurde in der letzten Stunde zu oft genutzt. "
            "Bitte später noch einmal versuchen.",
        )


# Reading PDFs into a fact list (F-58): every request counts, since the reading
# itself is work before the model is asked.
DOCUMENT_SUMMARIES_PER_HOUR = 20
# Reverses and follow-ups (F-60, F-61) together: only a draft the model is asked
# for counts; one already written is returned without it.
SCENARIO_DRAFTS_PER_HOUR = 20


def fresh() -> tuple[CallSlots, RateLimit, RateLimit]:
    """New, empty counters for the three caps below."""
    return (
        CallSlots(MAX_OPEN_CALLS),
        RateLimit(DOCUMENT_SUMMARIES_PER_HOUR, _HOUR_S),
        RateLimit(SCENARIO_DRAFTS_PER_HOUR, _HOUR_S),
    )


# Read as `limits.OPEN_CALLS` etc. at the call site, never imported by name, so
# the test suite can start each test from `fresh()` ones.
OPEN_CALLS, DOCUMENT_SUMMARIES, SCENARIO_DRAFTS = fresh()
