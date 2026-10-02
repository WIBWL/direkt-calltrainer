"""Sessions expire after six months unless the subject says otherwise (ADR 0067).

Consent answers whether data may be stored; this answers how long. The sweep
asks Postgres what is expired each run, so a missed run delays a deletion but
never cancels it (a Redis job scheduled months ahead would not survive a restart)."""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session as DbSession

from backend import deletion
from backend.db import models as db_models

logger = logging.getLogger(__name__)

# How long a stored Session is kept. Six months: long enough to look back over
# a training period, short enough that nobody's recorded speech sits around for
# years on the strength of one click.
RETENTION = timedelta(days=182)


def cutoff(now: datetime | None = None) -> datetime:
    """Sessions that started before this are due for deletion. `now` is
    injectable for tests and so one sweep uses a single instant."""
    return (now or datetime.now(UTC)) - RETENTION


def auto_delete_enabled(db: DbSession, subject_id: str) -> bool:
    """Whether the sweep applies to this subject. True unless they said no.

    The default is the *absence* of a row, which makes retention a policy
    rather than an opt-in.
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
    """Delete every expired Session whose subject has not opted out. Returns how many.

    Idempotent. Subjects come from the expired Sessions, not the preference table,
    since most subjects have no row there. Goes through `deletion.remove` (ORM
    cascades, follow-ups retired, reverses removed unless still played on)."""
    boundary = cutoff(now)
    expired = (
        db.query(db_models.Session)
        .filter(db_models.Session.started_at < boundary)
        .all()
    )
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
        # One savepoint per subject: otherwise one failure rolls back every
        # subject's deletion, and the next run hits the same row -- turning one
        # stuck subject into no retention at all (ADR 0067).
        try:
            with db.begin_nested():
                # Reverses carry a briefing from the call's own wrap-up, so they
                # expire with it (ADR 0070's addendum); nobody decides here.
                deletion.remove(db, sessions, with_reverses=True)
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                "Retention sweep: could not delete the expired sessions of one subject; "
                "the others are unaffected and the next run tries again"
            )
            continue
        deleted += len(sessions)

    # Orphaned reverses, on every run: once `origin_session_id` is cleared, a
    # reverse spared earlier or left by a hand deletion is found only by age.
    deletion.delete_unreferenced_reverses(db, deletion.orphaned_reverses(db, boundary))
    if deleted or suspended:
        logger.info(
            "Retention sweep: deleted %d session(s) older than %s; %d subject(s) had it suspended",
            deleted, boundary.date(), suspended,
        )
    return deleted


def sweep_now() -> int:
    """Run one sweep in its own transaction. For the scheduled caller.

    Raises rather than swallowing: a sweep that silently stops is a retention
    period that silently stops existing.
    """
    # Imported here so importing this module never requires a database.
    from backend.db.session import session_scope  # pylint: disable=import-outside-toplevel

    with session_scope() as db:
        return sweep(db)
