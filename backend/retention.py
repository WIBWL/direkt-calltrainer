"""Sessions expire after six months unless the subject says otherwise
(ADR 0061).

Consent answers whether data may be stored; this answers how long. Without it
a training recorded today is still there in four years, and "we keep it until
someone asks us not to" is not a retention period, it is the absence of one.

The sweep is driven from Postgres, not from a timer: it asks which Sessions are
older than the period every time it runs, so a missed run delays a deletion but
never cancels it. A job scheduled six months ahead in Redis would be gone after
one restart, and nothing would ever notice.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session as DbSession

from backend.db import models as db_models

logger = logging.getLogger(__name__)

# How long a stored Session is kept. Six months: long enough to look back over
# a training period, short enough that nobody's recorded speech sits around for
# years on the strength of one click.
RETENTION = timedelta(days=182)


def cutoff(now: datetime | None = None) -> datetime:
    """Sessions that started before this are due for deletion.

    `now` is injectable so a test can place the boundary rather than wait for
    it, and so a caller sweeping several subjects uses one instant for all of
    them instead of drifting across the loop.
    """
    return (now or datetime.now(UTC)) - RETENTION


def auto_delete_enabled(db: DbSession, subject_id: str) -> bool:
    """Whether the sweep applies to this subject. True unless they said no.

    The default lives here, in the absence of a row, rather than in a row
    written at first login: a subject who never touched the setting is covered
    by the retention period, which is what makes it a policy rather than an
    opt-in.
    """
    row = (
        db.query(db_models.RetentionPreference)
        .filter_by(subject_id=subject_id)
        .one_or_none()
    )
    return True if row is None else row.auto_delete


def set_auto_delete(db: DbSession, subject_id: str, enabled: bool) -> None:
    """Record the subject's choice. Idempotent: repeating it changes nothing
    but the timestamp."""
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
    """When a Session recorded at `started_at` is due to be deleted."""
    return started_at + RETENTION


def next_expiry(db: DbSession, subject_id: str) -> datetime | None:
    """When this subject's oldest Session falls due, or None if none will.

    None also when the subject has suspended the sweep: the interface should
    then say nothing about a date, because there is not going to be one.
    """
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
    """Delete every expired Session whose subject has not opted out.

    Returns how many went. Idempotent, and safe to run as often as anyone
    likes: a second run finds nothing left over the line.

    Subjects are resolved from the expired Sessions themselves rather than from
    the preference table, because most subjects have no preference row at all:
    that absence is the default, and iterating the table would sweep only the
    people who had already thought about it.

    Deletes through the ORM, like `deletion.py`, so the same ownership cascades
    take the Turns, Measurements, Feedback and jobs with each Session
    (ADR 0026/0052).
    """
    boundary = cutoff(now)
    expired = (
        db.query(db_models.Session)
        .filter(db_models.Session.started_at < boundary)
        .all()
    )
    if not expired:
        return 0

    # Grouped so the preference is read once per subject rather than once per
    # Session, and so the log line below counts people rather than rows.
    by_subject: dict[str, list[db_models.Session]] = {}
    for session in expired:
        by_subject.setdefault(session.subject_id, []).append(session)

    deleted = 0
    suspended = 0
    for subject_id, sessions in by_subject.items():
        if not auto_delete_enabled(db, subject_id):
            suspended += 1
            continue
        for session in sessions:
            db.delete(session)
        deleted += len(sessions)

    db.flush()
    if deleted or suspended:
        logger.info(
            "Retention sweep: deleted %d session(s) older than %s; %d subject(s) had it suspended",
            deleted, boundary.date(), suspended,
        )
    return deleted


def sweep_now() -> int:
    """Run one sweep in its own transaction. For the scheduled caller.

    Failures are raised, not swallowed: unlike the live path, nothing here is
    waiting on an answer, and a sweep that silently stops running is a
    retention period that silently stops existing.
    """
    # Imported here so importing this module never requires a database.
    from backend.db.session import session_scope  # pylint: disable=import-outside-toplevel

    with session_scope() as db:
        return sweep(db)
