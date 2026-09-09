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
construction: those foreign keys carry no `ondelete` at all. The one Scenario
that belongs to a Session — the follow-up drafted from its feedback (ADR 0069)
— is deactivated rather than deleted, for the reason `retire_follow_ups` gives.

One exception, and only on the withdrawal path: a reverse Scenario (ADR 0070)
is content about the subject's own call rather than reference data, so
`delete_subject_sessions` removes those rows too. Deleting a *single* training
does not — see `_delete_reverses` for why the two differ.

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


def retire_follow_ups(db: DbSession, sessions: list[db_models.Session]) -> None:
    """Deactivate the follow-up Scenarios drafted from these Sessions (ADR 0069).

    Deactivated rather than deleted, and this is the one place that decides it:
    a later Session may have been played on such a Scenario, `session.scenario_id`
    is NOT NULL and carries no `ondelete` (ADR 0026), and that training has to
    stay readable. `active = False` is what reference rows retired from the seed
    already use — it takes the row out of the library and leaves everything that
    points at it intact.

    Called before the Sessions go, from every path that removes one: the
    withdrawal and the single delete below, and the retention sweep
    (`backend/retention.py`). The column's `ON DELETE SET NULL` then clears the
    provenance, so this is not a place a raw-SQL delete can leave inconsistent —
    only one where it would leave the Scenario on offer.
    """
    session_ids = [session.session_id for session in sessions]
    if not session_ids:
        return
    db.query(db_models.Scenario).filter(
        db_models.Scenario.derived_from_session_id.in_(session_ids)
    ).update({"active": False}, synchronize_session=False)


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
    retire_follow_ups(db, sessions)
    for session in sessions:
        db.delete(session)
    # Flushed here rather than left to the caller's commit, so a caller that
    # goes on to write in the same transaction (the withdrawal does) cannot
    # observe rows this call has logically already removed.
    db.flush()
    _delete_reverses(db, subject_id)
    logger.info("Deleted %d stored session(s) for the subject", len(sessions))
    return len(sessions)


def _delete_reverses(db: DbSession, subject_id: str) -> None:
    """Remove the subject's reverse Scenarios (ADR 0070).

    The one place where a withdrawal reaches beyond the `session` table, and
    deliberately: a reverse carries a briefing written from that person's own
    wrap-up, so leaving the row would leave a reading of feedback whose
    conversation has just been deleted. An ordinary authored Scenario is not
    touched — it is the User's own work about a case, not a record of a call
    they had.

    After the Sessions, never before: a reverse Session points at its Scenario
    through `session.scenario_id`, which carries no `ondelete` at all
    (ADR 0052), so this delete would be refused while such a row still stood.

    Hard-deleted rather than deactivated, unlike every other Scenario retirement
    (ADR 0058): deactivation keeps the text, and the text is what has to go.
    """
    reverses = (
        db.query(db_models.Scenario)
        .filter_by(created_by=subject_id, reverse=True)
        .all()
    )
    for scenario in reverses:
        db.delete(scenario)
    db.flush()
    if reverses:
        logger.info("Deleted %d reverse scenario(s) for the subject", len(reverses))


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
    retire_follow_ups(db, [session])
    db.delete(session)
    db.flush()
    logger.info("Deleted one stored session")
    return True
