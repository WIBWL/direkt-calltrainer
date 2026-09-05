"""The feedback job's state machine (ADR 0019/0032).

`GET /api/sessions/{extern_id}` serves the newest feedback job's status as the
Session's `status`, and the post-call screen polls on it: a row left at
"queued" or "running" is a spinner that stops only on the client's own timeout.

The row is created with the Session, in its transaction
(backend/session/persistence.py); every transition afterwards lives here.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session as DbSession

from backend.db import models as db_models
from backend.db.session import session_scope

# "done" and "failed" are terminal: a late writer must not turn a wrap-up the
# user can already read into an error.
_OPEN = frozenset({"queued", "running"})


def latest(db: DbSession, session_id: int) -> db_models.AnalysisJob | None:
    """This Session's newest feedback job, by id, or None if it has none."""
    return (
        db.query(db_models.AnalysisJob)
        .filter_by(session_id=session_id, kind="feedback")
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
        job = db_models.AnalysisJob(session_id=session_id, kind="feedback", attempts=0)
        db.add(job)
    job.status = status
    job.error_text = error_text
    job.updated_at = datetime.now()
    if status == "running":
        job.attempts += 1


def mark_failed(session_id: int, error_text: str) -> None:
    """Fail the job from outside the worker, in a transaction of its own.

    For the caller that has committed the row and then finds the work will
    never happen -- the enqueue to Redis failing after the Session was written.
    Not being the process that runs the job, it leaves a terminal state alone.

    Raises LookupError when the Session has no feedback job: the caller only
    reaches this after persisting one, so its absence is a bug, not a state.
    """
    with session_scope() as db:
        job = latest(db, session_id)
        if job is None:
            raise LookupError(f"Feedback job for session {session_id} does not exist")
        if job.status not in _OPEN:
            return
        job.status = "failed"
        job.error_text = error_text
        job.updated_at = datetime.now()
