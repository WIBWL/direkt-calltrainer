"""The feedback job's state machine (ADR 0019/0032).

`GET /api/sessions/{extern_id}` serves the newest feedback job's status as the
Session's `status`, and the post-call screen polls on it: a row left at
"queued" or "running" is a spinner that stops only on the client's own timeout.

The row is created with the Session, in its transaction
(backend/session/persistence.py); every transition afterwards lives here.
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

# How long a queued job may wait before it is considered stale, and how long one
# may run. Generous: the wrap-up is a single LLM call against a gateway that is
# occasionally slow, and nobody is blocked while it works.
#
# It lives here rather than in `queue.py`, which owns the Redis side: every
# reader of it is asking the question below, and importing it from there meant
# pulling Redis into the REST layer -- which is why both readers deferred the
# import inside a function and then answered the question twice.
JOB_TIMEOUT_S = 300


def is_live(job: db_models.AnalysisJob, *, include_queued: bool) -> bool:
    """Whether this job may still be working.

    False for a terminal row, and for one that has not moved in longer than a
    job may run: the worker holding it is gone -- killed, timed out, or
    restarted -- and nothing will ever move it off `running`, which is the gap
    ADR 0032 names.

    `include_queued` is the one thing the two callers differ on, so it is a
    parameter rather than a second copy of this. A reader deciding what to show
    (`api/sessions.py`) asks about a *running* row only: a queued one is not
    abandoned, it is waiting. A writer deciding whether to queue a second job
    (`scripts/requeue_feedback.py`) must count a queued one as working, or it
    queues a duplicate and both write the same Session.

    They did answer it separately, and differently: one coerced a naive
    timestamp and the other would have raised on it, one guarded against a
    missing timestamp and the other did not. Both defences are here now.
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


def latest(db: DbSession, session_id: int) -> db_models.AnalysisJob | None:
    """This Session's newest feedback job, by id, or None if it has none."""
    return (
        db.query(db_models.AnalysisJob)
        .filter_by(session_id=session_id, kind=db_models.JOB_KIND_FEEDBACK)
        .order_by(db_models.AnalysisJob.job_id.desc())
        .first()
    )


def mark(db: DbSession, session_id: int, status: str, error_text: str | None = None) -> None:
    """Move the job to `status`, inside the caller's transaction.

    The worker's own writer: it runs the job, so it overwrites whatever state
    it finds, and creates the row where a Session has none.
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
    """Fail the job from outside the worker, in a transaction of its own.

    For the caller that has committed the row and then finds the work will
    never happen -- the enqueue to Redis failing after the Session was written.
    Not being the process that runs the job, it leaves a terminal state alone.

    Never raises. Every caller is already handling a failure of its own and
    must not be handed a second one; the status row is worth less than the
    transcript on its way to the user either way.
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
