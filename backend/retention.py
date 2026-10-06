"""Six-month retention (ADR 0067). Each sweep asks Postgres what is expired, so a
missed run only delays deletion."""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session as DbSession

from shared.db import models as db_models
from backend import deletion

logger = logging.getLogger(__name__)

RETENTION = timedelta(days=182)


def cutoff(now: datetime | None = None) -> datetime:
    """`now` is injectable, and lets one sweep use one instant."""
    return (now or datetime.now(UTC)) - RETENTION


def auto_delete_enabled(db: DbSession, subject_id: str) -> bool:
    """True unless the subject switched it off: no row means the default."""
    row = (
        db.query(db_models.RetentionPreference)
        .filter_by(subject_id=subject_id)
        .one_or_none()
    )
    return True if row is None else row.auto_delete


def set_auto_delete(db: DbSession, subject_id: str, enabled: bool) -> None:
    row = (
        db.query(db_models.RetentionPreference)
        .filter_by(subject_id=subject_id)
        .one_or_none()
    )
    if row is None:
        row = db_models.RetentionPreference(subject_id=subject_id, auto_delete=enabled,
                                            updated_at=datetime.now(UTC))
        db.add(row)
    else:
        row.auto_delete = enabled
        row.updated_at = datetime.now(UTC)
    db.flush()
    logger.info("Retention sweep %s for one subject", "enabled" if enabled else "suspended")


def expires_at(started_at: datetime) -> datetime:
    return started_at + RETENTION


def next_expiry(db: DbSession, subject_id: str) -> datetime | None:
    """None if none will, including when the sweep is suspended."""
    if not auto_delete_enabled(db, subject_id):
        return None
    oldest = (
        db.query(db_models.Session)
        .filter_by(subject_id=subject_id)
        .order_by(db_models.Session.started_at.asc())
        .first()
    )
    return expires_at(oldest.started_at) if oldest else None


def sweep(db: DbSession, now: datetime | None = None) -> int:
    """Returns how many were deleted. Goes through `deletion.remove`."""
    boundary = cutoff(now)
    expired = (
        db.query(db_models.Session)
        .filter(db_models.Session.started_at < boundary)
        .all()
    )
    by_subject: dict[str, list[db_models.Session]] = {}
    for session in expired:
        by_subject.setdefault(session.subject_id, []).append(session)

    deleted = 0
    suspended = 0
    for subject_id, sessions in by_subject.items():
        if not auto_delete_enabled(db, subject_id):
            suspended += 1
            continue
        # One savepoint per subject, so one stuck subject cannot stop retention for all.
        try:
            with db.begin_nested():
                deletion.remove(db, sessions, with_reverses=True)
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                "Retention sweep: could not delete the expired sessions of one subject; "
                "the others are unaffected and the next run tries again"
            )
            continue
        deleted += len(sessions)

    # Orphaned reverses are found only by age once their origin link is cleared.
    deletion.delete_unreferenced_reverses(db, deletion.orphaned_reverses(db, boundary))
    if deleted or suspended:
        logger.info(
            "Retention sweep: deleted %d session(s) older than %s; %d subject(s) had it suspended",
            deleted, boundary.date(), suspended,
        )
    return deleted


def sweep_now() -> int:
    """Raises rather than swallowing: a silently stopped sweep is no retention."""
    from shared.db.session import session_scope  # pylint: disable=import-outside-toplevel

    with session_scope() as db:
        return sweep(db)
