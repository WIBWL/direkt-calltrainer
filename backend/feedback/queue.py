"""The job queue between the live Session and the Feedback worker (ADR 0019).

Deliberately thin: one queue, one job type. Everything the worker needs is
already in Postgres by the time the job runs (ADR 0034/0048), so the payload is
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
JOB_TIMEOUT_S = 300
_RESULT_TTL_S = 3600

# How long the *enqueue* may take, which is a different question entirely: it
# happens while the user waits for their transcript. See `connection()`.
CONNECT_TIMEOUT_S = 3
SOCKET_TIMEOUT_S = 5


@lru_cache(maxsize=1)
def connection() -> Redis:
    """The process-wide Redis connection, created on first use.

    Read lazily like the database settings in backend/db/session.py, so importing this
    module never requires a configured environment.

    Deliberately without a read timeout: this is the worker's connection, and
    the worker spends most of its life blocked on it waiting for a job. A
    socket timeout shorter than that block would turn the normal idle state
    into an error. The app side gets its own connection below.
    """
    return Redis.from_url(_url())


@lru_cache(maxsize=1)
def _enqueue_connection() -> Redis:
    """The app's connection, which only ever pushes a job and waits for the ack.

    Timed out for the same reason the database connection is (backend/db/
    session.py): `enqueue_feedback` runs on a threadpool thread while the user
    waits for their transcript, and `session.ended` goes out only once it
    returns. A *refused* connection fails at once, but a Redis that merely
    stops answering -- a paused container, a dropped packet, a swapped-out
    process -- would hold that thread until the OS gave up minutes later, and
    the user would never get the transcript. Without consent that transcript is
    the only copy of the call there is (F-64, ADR 0034/0066). A queue push is
    local and tiny, so seconds are generous; the job itself is bounded by
    JOB_TIMEOUT_S and has nothing to do with this.
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
