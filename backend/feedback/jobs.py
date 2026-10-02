"""The feedback job's state machine (ADR 0019/0032). The post-call screen polls
the newest job's status, so a row stuck open is a spinner that never ends. The
row is created with the Session (session/persistence.py); every later
transition lives here.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session as DbSession

from backend.db import models as db_models
from backend.db.session import session_scope

logger = logging.getLogger(__name__)

# "done" and "failed" are terminal: a late writer must not turn a wrap-up the
# user can already read into an error.
_OPEN = frozenset({db_models.JOB_QUEUED, db_models.JOB_RUNNING})

# How long a job may wait or run before it is stale. Generous: one LLM call on
# an occasionally slow gateway. Here rather than in `queue.py` so asking
# `is_live` does not pull Redis into the REST layer.
JOB_TIMEOUT_S = 300


def is_live(job: db_models.AnalysisJob, *, include_queued: bool) -> bool:
    """Whether this job may still be working: open and moved within JOB_TIMEOUT_S
    (a dead worker never moves it off `running`, ADR 0032). A reader asks with
    `include_queued=False`; a writer deciding whether to queue again must pass
    True, or it queues a duplicate that races the first.
    """
    if job.status not in _OPEN:
        return False
    if job.status == db_models.JOB_QUEUED and not include_queued:
        return False
    updated = job.updated_at
    if updated is None:
        # The column is NOT NULL, so this is a row nobody wrote through `mark`.
        # Nothing can be said about its age; it is not working.
        return False
    # A timestamptz reads back tz-aware, but comparing an aware and a naive
    # datetime raises -- and a 500 here would cost the user a wrap-up that
    # exists.
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=UTC)
    return datetime.now(UTC) - updated <= timedelta(seconds=JOB_TIMEOUT_S)


def newest(session: db_models.Session) -> db_models.AnalysisJob | None:
    """The newest feedback job of a Session already loaded, or None -- `latest`
    for a caller holding the row rather than a primary key.
    """
    found = [job for job in session.jobs if job.kind == db_models.JOB_KIND_FEEDBACK]
    return max(found, key=lambda job: job.job_id) if found else None


# Why a wrap-up cannot be asked for again. Machine-readable, so the route can
# turn each into its own sentence and a test can name the case.
BLOCKED_DONE = "done"
BLOCKED_EMPTY = "empty"
BLOCKED_WORKING = "working"


def retry_blocked(session: db_models.Session) -> str | None:
    """Why this Session's wrap-up may not be queued again, or None if it may; the
    one rule for `api/sessions.py` and `scripts/requeue_feedback.py`. Refusals:
    `done` (a wrap-up exists), `empty` (no Turns), `working` (queued counts). A
    job saying `done` with no wrap-up is deliberately *not* refused.
    """
    if session.feedback is not None:
        return BLOCKED_DONE
    if not session.turns:
        return BLOCKED_EMPTY
    job = newest(session)
    if job is not None and is_live(job, include_queued=True):
        return BLOCKED_WORKING
    return None


def latest(db: DbSession, session_id: int) -> db_models.AnalysisJob | None:
    """This Session's newest feedback job, by id, or None if it has none."""
    return (
        db.query(db_models.AnalysisJob)
        .filter_by(session_id=session_id, kind=db_models.JOB_KIND_FEEDBACK)
        .order_by(db_models.AnalysisJob.job_id.desc())
        .first()
    )


def mark(db: DbSession, session_id: int, status: str, error_text: str | None = None) -> None:
    """Move the job to `status`, inside the caller's transaction. The worker's
    writer: it overwrites any state and creates the row if missing.
    """
    job = latest(db, session_id)
    if job is None:
        job = db_models.AnalysisJob(
            session_id=session_id, kind=db_models.JOB_KIND_FEEDBACK, attempts=0
        )
        db.add(job)
    job.status = status
    job.error_text = error_text
    # Timezone-aware: the column is, and a naive value would shift with the
    # container's TZ.
    job.updated_at = datetime.now(UTC)
    if status == db_models.JOB_RUNNING:
        job.attempts += 1


def mark_failed(session_id: int, error_text: str) -> None:
    """Fail the job from outside the worker (e.g. the enqueue failed), in its own
    transaction, leaving a terminal state alone. Never raises: every caller is
    already handling a failure of its own.
    """
    try:
        with session_scope() as db:
            job = latest(db, session_id)
            if job is None:
                logger.warning("No feedback job to fail for session %d", session_id)
                return
            if job.status not in _OPEN:
                return
            job.status = db_models.JOB_FAILED
            job.error_text = error_text
            job.updated_at = datetime.now(UTC)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Feedback job could not be failed for session %d", session_id)
