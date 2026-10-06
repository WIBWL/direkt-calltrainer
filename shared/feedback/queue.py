"""The wrap-up job queue (ADR 0019). The payload is only a Session key."""

from __future__ import annotations

from functools import lru_cache

from redis import Redis
from rq import Queue

from shared.env import required
from shared.feedback.jobs import JOB_TIMEOUT_S

QUEUE_NAME = "feedback"

# By name, so the backend never imports the worker. Renaming the generator
# fails every job silently; test_job_name pins it.
JOB_FUNCTION = "worker.generator.generate_feedback"

_RESULT_TTL_S = 3600

# The enqueue happens while the user waits for their transcript.
CONNECT_TIMEOUT_S = 3
SOCKET_TIMEOUT_S = 5


@lru_cache(maxsize=1)
def connection() -> Redis:
    """The worker's connection: no read timeout, since it idles blocked on it."""
    return Redis.from_url(_url())


@lru_cache(maxsize=1)
def _enqueue_connection() -> Redis:
    """The app's connection, timed out because the user waits on the enqueue."""
    return Redis.from_url(
        _url(),
        socket_connect_timeout=CONNECT_TIMEOUT_S,
        socket_timeout=SOCKET_TIMEOUT_S,
    )


def _url() -> str:
    # Read lazily: importing this module must not require REDIS_URL.
    return required("REDIS_URL")


@lru_cache(maxsize=1)
def _queue() -> Queue:
    return Queue(QUEUE_NAME, connection=_enqueue_connection())


def enqueue_feedback(session_id: int) -> None:
    _queue().enqueue(JOB_FUNCTION, session_id, job_timeout=JOB_TIMEOUT_S, result_ttl=_RESULT_TTL_S)
