"""Deleting a subject's stored trainings (ADR 0066) -- the one place that removes user data.

Cascades take a Session's subtree (ADR 0026/0052); reference data is untouched. Follow-ups
are deactivated (ADR 0069); reverses (ADR 0070) are hard-deleted by withdrawal and sweep,
not by a single hand deletion. All paths go through `remove` (ADR 0102). Backups: ADR 0066."""
from __future__ import annotations

import logging
from datetime import datetime
import uuid

from sqlalchemy.orm import Session as DbSession

from backend.db import models as db_models

logger = logging.getLogger(__name__)


def remove(
    db: DbSession, sessions: list[db_models.Session], *, with_reverses: bool
) -> None:
    """Delete these Sessions and what goes with them, in the one order that works.

    1. retire follow-ups; 2. with `with_reverses`, read the reverses *before* the
    delete (`origin_session_id` is `ON DELETE SET NULL`, so the link vanishes);
    3. delete the Sessions; 4. delete those reverses nothing still plays on.
    Without `with_reverses` they stay (a single hand deletion, ADR 0070 addendum).
    Flushed before returning, so later writes in the transaction see the removal."""
    retire_follow_ups(db, sessions)
    reverse_ids = reverses_of(db, sessions) if with_reverses else []
    for session in sessions:
        db.delete(session)
    db.flush()
    if reverse_ids:
        delete_unreferenced_reverses(db, reverse_ids)


def retire_follow_ups(db: DbSession, sessions: list[db_models.Session]) -> None:
    """Deactivate the follow-up Scenarios drafted from these Sessions (ADR 0069).

    Not deleted: a later Session may have been played on one, and
    `session.scenario_id` is NOT NULL with no `ondelete` (ADR 0026). Called by
    `remove` before the Sessions go; `ON DELETE SET NULL` then clears provenance."""
    session_ids = [session.session_id for session in sessions]
    if not session_ids:
        return
    db.query(db_models.Scenario).filter(
        db_models.Scenario.derived_from_session_id.in_(session_ids)
    ).update({"active": False}, synchronize_session=False)


def reverses_of(db: DbSession, sessions: list[db_models.Session]) -> list[int]:
    """The reverse Scenarios replaying these Sessions, by primary key.

    Must be read *before* the Sessions go: `origin_session_id` is
    `ON DELETE SET NULL` (ADR 0070). Public for the retention dry run; what may
    actually be deleted is `delete_unreferenced_reverses`'s decision."""
    session_ids = [session.session_id for session in sessions]
    if not session_ids:
        return []
    return [
        row.scenario_id
        for row in db.query(db_models.Scenario)
        .filter(db_models.Scenario.origin_session_id.in_(session_ids))
        .all()
    ]


def orphaned_reverses(db: DbSession, boundary: datetime) -> list[int]:
    """Reverse Scenarios older than `boundary` whose origin Session is gone.

    With the origin deleted the link-based lookup cannot find them, and their
    `reverse_brief` would outlive the period (ADR 0067/0070). Found by age instead;
    `delete_unreferenced_reverses` still spares one being played."""
    return [
        row.scenario_id
        for row in db.query(db_models.Scenario)
        .filter(
            db_models.Scenario.reverse.is_(True),
            db_models.Scenario.origin_session_id.is_(None),
            db_models.Scenario.created_at < boundary,
        )
        .all()
    ]


def delete_unreferenced_reverses(db: DbSession, scenario_ids: list[int]) -> int:
    """Delete those of `scenario_ids` no Session points at any more.

    A reverse may still carry a live `session.scenario_id` (no `ondelete`, ADR 0052);
    deleting it would be refused and abort the whole sweep, so it waits for a later
    run. Hard-deleted: deactivation would keep the briefing text."""
    if not scenario_ids:
        return 0
    still_played = {
        scenario_id
        for (scenario_id,) in db.query(db_models.Session.scenario_id)
        .filter(db_models.Session.scenario_id.in_(scenario_ids))
        .distinct()
    }
    doomed = [
        db.get(db_models.Scenario, scenario_id)
        for scenario_id in scenario_ids
        if scenario_id not in still_played
    ]
    for scenario in doomed:
        if scenario is not None:
            db.delete(scenario)
    db.flush()
    if doomed:
        logger.info("Deleted %d expired reverse scenario(s)", len(doomed))
    return len(doomed)


def delete_subject_sessions(db: DbSession, subject_id: str) -> int:
    """Delete every stored Session of one subject. Returns how many went.

    Idempotent, so a retried or double-clicked withdrawal is not an error.
    Through the ORM rather than a bulk DELETE: ORM and database cascades are
    declared as a pair (ADR 0026), and relying on only one lets the other rot."""
    sessions = db.query(db_models.Session).filter_by(subject_id=subject_id).all()
    remove(db, sessions, with_reverses=True)
    # Every other reverse of this subject's too: one whose training was deleted
    # by hand earlier lost its link to it and is not among the reverses of the
    # Sessions just removed.
    _delete_reverses(db, subject_id)
    logger.info("Deleted %d stored session(s) for the subject", len(sessions))
    return len(sessions)


def _delete_reverses(db: DbSession, subject_id: str) -> None:
    """Remove the subject's reverse Scenarios (ADR 0070): their briefing comes from
    the person's own wrap-up. Must run *after* the Sessions (`session.scenario_id`
    has no `ondelete`, ADR 0052). Hard-deleted, unlike other retirements (ADR 0058),
    because the text itself is what has to go."""
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

    Ownership is in the query (as in ADR 0064's history). Absent and not-yours
    both return False -- deliberately indistinguishable (ADR 0031/0050).
    """
    session = (
        db.query(db_models.Session)
        .filter_by(extern_id=extern_id, subject_id=subject_id)
        .one_or_none()
    )
    if session is None:
        return False
    remove(db, [session], with_reverses=False)
    logger.info("Deleted one stored session")
    return True
