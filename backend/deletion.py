"""Deleting a subject's stored trainings (ADR 0066).

The one place that removes user data, so that every entry point — the consent
withdrawal today, a "delete this training" button later — goes through the same
code rather than each growing its own idea of what belongs to a person.

It is deliberately small, because the schema already does the work. Everything
a Session owns hangs off it with `ON DELETE CASCADE` and `passive_deletes=True`
(ADR 0026/0052), so deleting the Session rows removes their Turns, Measurements,
Findings, Feedback, FeedbackPoints and AnalysisJobs with them, by raw SQL as
well as through the ORM — which `tests/test_cascade_delete.py` already pins
down. Reference data (Persona, Scenario, Language, MetricType) is untouched by
construction: those foreign keys carry no `ondelete` at all.

What this module does *not* do is claim to be a complete erasure. Two limits
are known and named rather than papered over: backups are not reached (there is
no surgical delete from a snapshot), and the transcript that STT logged in
plaintext is not reached either. Both are recorded in ADR 0066.
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session as DbSession

from backend.db import models as db_models

logger = logging.getLogger(__name__)


def delete_subject_sessions(db: DbSession, subject_id: str) -> int:
    """Delete every stored Session of one subject. Returns how many went.

    Idempotent: a second call finds nothing and returns 0. That matters more
    than it looks — a withdrawal that is retried after a timeout must not
    become an error, and a user who clicks twice must not see a failure for
    work that already succeeded.

    Loaded and deleted through the ORM rather than issued as one bulk
    `DELETE ... WHERE subject_id = ...`. A bulk delete bypasses the ORM's
    cascade handling and would lean entirely on the database's, which happens
    to be correct here — but the two are declared as a pair on purpose
    (ADR 0026), and quietly relying on only one of them is how the other stops
    being maintained.
    """
    sessions = db.query(db_models.Session).filter_by(subject_id=subject_id).all()
    for session in sessions:
        db.delete(session)
    # Flushed here rather than left to the caller's commit, so a caller that
    # goes on to write in the same transaction (the withdrawal does) cannot
    # observe rows this call has logically already removed.
    db.flush()
    logger.info("Deleted %d stored session(s) for the subject", len(sessions))
    return len(sessions)


def delete_session(db: DbSession, subject_id: str, extern_id: uuid.UUID) -> bool:
    """Delete one of the subject's Sessions. True if there was one to delete.

    Ownership is part of the query, not a check on its result — the same shape
    the history uses (ADR 0064), and for the same reason: a filter cannot be
    forgotten on one path the way a comparison can, and there is no version of
    this call that should ever reach somebody else's row.

    Returns False rather than raising for an id that is absent *or* not the
    caller's. The two are deliberately indistinguishable (ADR 0031/0050), and
    the route turns this into the same 404 a stale link gets — telling the
    caller that an id exists but is not theirs is exactly what the unguessable
    id is there to withhold.
    """
    session = (
        db.query(db_models.Session)
        .filter_by(extern_id=extern_id, subject_id=subject_id)
        .one_or_none()
    )
    if session is None:
        return False
    db.delete(session)
    db.flush()
    logger.info("Deleted one stored session")
    return True
