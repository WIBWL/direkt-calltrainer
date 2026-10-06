"""Whether a subject has agreed to their trainings being stored (ADR 0066)."""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session as DbSession

from shared.db import models as db_models
from shared.db.session import session_scope

logger = logging.getLogger(__name__)

# Bump on any substantive change to the notice: older decisions go stale.
CURRENT_VERSION = "2"

PURPOSE = db_models.CONSENT_SESSION_STORAGE


@dataclass(frozen=True)
class ConsentState:
    status: str | None  # granted, withdrawn, or None if never decided
    version: str | None
    decided_at: datetime | None

    @property
    def allows_storage(self) -> bool:
        return self.status == db_models.CONSENT_GRANTED and self.version == CURRENT_VERSION

    @property
    def decision_required(self) -> bool:
        # Not after a withdrawal: re-prompting would wear the subject down.
        if self.status == db_models.CONSENT_WITHDRAWN:
            return False
        return not self.allows_storage


def current(db: DbSession, subject_id: str) -> ConsentState:
    row = (
        db.query(db_models.Consent)
        .filter_by(subject_id=subject_id, purpose=PURPOSE)
        # By key, not timestamp: two decisions can share a second.
        .order_by(db_models.Consent.consent_id.desc())
        .first()
    )
    if row is None:
        return ConsentState(status=None, version=None, decided_at=None)
    return ConsentState(status=row.status, version=row.version, decided_at=row.decided_at)


def record_decision(db: DbSession, subject_id: str, granted: bool) -> ConsentState:
    """Append a decision unless it repeats the one in force."""
    status = db_models.CONSENT_GRANTED if granted else db_models.CONSENT_WITHDRAWN
    state = current(db, subject_id)
    if state.status == status and state.version == CURRENT_VERSION:
        return state

    row = db_models.Consent(
        subject_id=subject_id,
        purpose=PURPOSE,
        version=CURRENT_VERSION,
        status=status,
        decided_at=datetime.now(UTC),
    )
    db.add(row)
    db.flush()
    logger.info("Consent %s recorded (version %s)", status, CURRENT_VERSION)
    return ConsentState(status=status, version=CURRENT_VERSION, decided_at=row.decided_at)


def lock_subject(db: DbSession, subject_id: str) -> None:
    """Serialise a subject's consent decision against their Session writes, so a
    withdrawal cannot land between the check and the insert."""
    key = int.from_bytes(
        hashlib.blake2b(subject_id.encode("utf-8"), digest_size=8).digest(),
        "big", signed=True,
    )
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


def allows_storage(subject_id: str, db: DbSession | None = None) -> bool:
    """Fails closed: an unreadable decision means no storage."""
    if db is not None:
        return current(db, subject_id).allows_storage
    try:
        with session_scope() as own:
            return current(own, subject_id).allows_storage
    except Exception:  # pylint: disable=broad-except
        logger.exception("Consent could not be read; refusing to store the Session")
        return False
