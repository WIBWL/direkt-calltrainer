"""The job queue between the live Session and the Feedback worker (ADR 0019).
One queue, one job type; the payload is just a Session's primary key, since
everything else is in Postgres by then -- never a transcript or audio (ADR 0048).
"""

from __future__ import annotations

import os
from functools import lru_cache

from redis import Redis
from rq import Queue

from backend.feedback.generator import generate_feedback
from backend.feedback.jobs import JOB_TIMEOUT_S

QUEUE_NAME = "feedback"

# Bounds the job RQ runs, and the window a reader believes a `running` row for
# (`jobs.is_live`). Defined beside that reading rather than here, so asking the
# question does not require Redis.
_RESULT_TTL_S = 3600

# How long the *enqueue* may take, which is a different question entirely: it
# happens while the user waits for their transcript. See `connection()`.
CONNECT_TIMEOUT_S = 3
SOCKET_TIMEOUT_S = 5


@lru_cache(maxsize=1)
def connection() -> Redis:
    """The worker's process-wide Redis connection, created lazily on first use.
    Deliberately without a read timeout: the worker idles blocked on it, and a
    timeout would turn that into an error. The app has its own connection below.
    """
    return Redis.from_url(_url())


@lru_cache(maxsize=1)
def _enqueue_connection() -> Redis:
    """The app's connection, which only pushes a job. Timed out because the user
    waits on it for their transcript -- possibly the only copy (F-64, ADR 0066)
    -- and a Redis that stops answering would otherwise hold it for minutes.
    """
    return Redis.from_url(
        _url(),
        socket_connect_timeout=CONNECT_TIMEOUT_S,
        socket_timeout=SOCKET_TIMEOUT_S,
    )


def _url() -> str:
    return os.environ.get("REDIS_URL", "redis://localhost:6379")


@lru_cache(maxsize=1)
def _queue() -> Queue:
    return Queue(QUEUE_NAME, connection=_enqueue_connection())


def enqueue_feedback(session_id: int) -> None:
    """Hand one finished Session to the worker. Raises if Redis is unreachable."""
    _queue().enqueue(generate_feedback, session_id, job_timeout=JOB_TIMEOUT_S, result_ttl=_RESULT_TTL_S)
