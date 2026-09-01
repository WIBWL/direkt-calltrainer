"""The job queue between the live Session and the Feedback worker (ADR 0019).

Deliberately thin: one queue, one job type. Everything the worker needs is
already in Postgres by the time the job runs (ADR 0034/0045), so the payload is
just a Session's primary key -- no transcript, and above all no audio.
"""

from __future__ import annotations

import os
from functools import lru_cache

from redis import Redis
from rq import Queue

from backend.feedback.generator import generate_feedback

QUEUE_NAME = "feedback"

# How long a queued job may wait before it is considered stale, and how long
# one may run. Generous: the wrap-up is a single LLM call against a gateway
# that is occasionally slow, and nobody is blocked while it works.
_JOB_TIMEOUT_S = 300
_RESULT_TTL_S = 3600


@lru_cache(maxsize=1)
def connection() -> Redis:
    """The process-wide Redis connection, created on first use.

    Read lazily like DATABASE_URL in backend/db/session.py, so importing this
    module never requires a configured environment.
    """
    return Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379"))


@lru_cache(maxsize=1)
def _queue() -> Queue:
    return Queue(QUEUE_NAME, connection=connection())


def enqueue_feedback(session_id: int) -> None:
    """Hand one finished Session to the worker. Raises if Redis is unreachable."""
    _queue().enqueue(generate_feedback, session_id, job_timeout=_JOB_TIMEOUT_S, result_ttl=_RESULT_TTL_S)
