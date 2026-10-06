"""The one place that removes user data (ADR 0066, 0102). Follow-ups are
deactivated; reverses are hard-deleted by withdrawal and sweep, not by a single
deletion (ADR 0070)."""
from __future__ import annotations

import logging
from datetime import datetime
import uuid

from sqlalchemy.orm import Session as DbSession

from shared.db import models as db_models

logger = logging.getLogger(__name__)


def remove(
    db: DbSession, sessions: list[db_models.Session], *, with_reverses: bool
) -> None:
    """In the one order that works: retire follow-ups; read the reverses before
    the delete (SET NULL unties them); delete; then delete reverses nothing still
    plays. Flushed before returning."""
    retire_follow_ups(db, sessions)
    reverse_ids = reverses_of(db, sessions) if with_reverses else []
    for session in sessions:
        db.delete(session)
    db.flush()
    if reverse_ids:
        delete_unreferenced_reverses(db, reverse_ids)


def retire_follow_ups(db: DbSession, sessions: list[db_models.Session]) -> None:
    """Deactivated, not deleted: a later Session may have played one (ADR 0069)."""
    session_ids = [session.session_id for session in sessions]
    if not session_ids:
        return
    db.query(db_models.Scenario).filter(
        db_models.Scenario.derived_from_session_id.in_(session_ids)
    ).update({"active": False}, synchronize_session=False)


def reverses_of(db: DbSession, sessions: list[db_models.Session]) -> list[int]:
    """Read before the Sessions go: `origin_session_id` is SET NULL."""
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
    """Found by age once the origin link is gone, so the brief cannot outlive the period."""
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
    """One still played would be refused (no `ondelete`) and abort the sweep, so
    it waits. Hard-deleted: deactivation would keep the briefing text."""
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
    """Idempotent. Through the ORM, not bulk DELETE: ORM and DB cascades are a
    pair (ADR 0026), and relying on one lets the other rot."""
    sessions = db.query(db_models.Session).filter_by(subject_id=subject_id).all()
    remove(db, sessions, with_reverses=True)
    # Also reverses whose link was cleared by an earlier single deletion.
    _delete_reverses(db, subject_id)
    logger.info("Deleted %d stored session(s) for the subject", len(sessions))
    return len(sessions)


def _delete_reverses(db: DbSession, subject_id: str) -> None:
    """After the Sessions (no `ondelete`); hard-deleted because the text must go."""
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
    """Ownership in the query; absent and foreign both return False (ADR 0050)."""
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
