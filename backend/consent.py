"""Whether a subject has agreed to their trainings being stored (ADR 0066).

The single place that answers it; the write path's answer is the one that must
be right. Decisions are appended, never overwritten (`record_decision` appends,
`current` reads the newest), so a withdrawal is distinct from never agreeing."""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session as DbSession

from backend.db import models as db_models
from backend.db.session import session_scope

logger = logging.getLogger(__name__)

# The wording currently shown. Bump this whenever the notice changes in
# substance: every decision recorded against an older version becomes stale and
# the subject is asked again. Consent to a text nobody put in front of them is
# not consent, so a silent edit of the notice must not keep an old "yes" alive.
CURRENT_VERSION = "1"

PURPOSE = db_models.CONSENT_SESSION_STORAGE


@dataclass(frozen=True)
class ConsentState:
    """What is known about one subject's decision, as the client needs it."""

    status: str | None
    """`granted`, `withdrawn`, or None where no decision was ever recorded."""

    version: str | None
    """The wording that decision was made against; None with no decision."""

    decided_at: datetime | None

    @property
    def allows_storage(self) -> bool:
        """True only for a live `granted` against the *current* wording; agreeing
        to an older notice is not agreeing to this one."""
        return self.status == db_models.CONSENT_GRANTED and self.version == CURRENT_VERSION

    @property
    def decision_required(self) -> bool:
        """True when the interface has to ask: no decision or a stale one.
        Not after a withdrawal -- re-prompting would wear the subject down."""
        if self.status == db_models.CONSENT_WITHDRAWN:
            return False
        return not self.allows_storage


def current(db: DbSession, subject_id: str) -> ConsentState:
    """The subject's newest decision, or an empty state if they never made one."""
    row = (
        db.query(db_models.Consent)
        .filter_by(subject_id=subject_id, purpose=PURPOSE)
        # By primary key, not by timestamp: two decisions in the same second
        # are possible and `decided_at` would order them arbitrarily, which for
        # a grant followed by a withdrawal is the difference between storing
        # someone's data and not.
        .order_by(db_models.Consent.consent_id.desc())
        .first()
    )
    if row is None:
        return ConsentState(status=None, version=None, decided_at=None)
    return ConsentState(status=row.status, version=row.version, decided_at=row.decided_at)


def record_decision(db: DbSession, subject_id: str, granted: bool) -> ConsentState:
    """Append a decision. Returns the state that now holds.

    Repeating the decision already in force writes nothing (double clicks);
    a decision that changes something is always written.
    """
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
    db.flush()  # so a caller in the same transaction reads this decision back
    logger.info("Consent %s recorded (version %s)", status, CURRENT_VERSION)
    return ConsentState(status=status, version=CURRENT_VERSION, decided_at=row.decided_at)


def lock_subject(db: DbSession, subject_id: str) -> None:
    """Serialise this subject's consent decision against their Session writes.

    Taken by the write path before reading the decision and by `POST /api/consent`
    before recording a withdrawal. Without it a write can read "granted", the
    withdrawal commit and delete, and the write then insert a Session no deletion
    path will ever visit (ADR 0066). Transaction-scoped, keyed on the subject."""
    key = int.from_bytes(
        hashlib.blake2b(subject_id.encode("utf-8"), digest_size=8).digest(),
        "big", signed=True,
    )
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


def allows_storage(subject_id: str, db: DbSession | None = None) -> bool:
    """Whether this subject's finished Sessions may be written.

    With `db`, answered inside the caller's transaction so the answer and the
    INSERT commit together under `lock_subject`; a failure propagates and aborts.
    Without `db` it opens its own. **Fails closed** either way: unlike everywhere
    else in the app, a database failure here must not be stepped over, since that
    would store data on a guess."""
    if db is not None:
        return current(db, subject_id).allows_storage
    try:
        with session_scope() as own:
            return current(own, subject_id).allows_storage
    except Exception:  # pylint: disable=broad-except
        logger.exception("Consent could not be read; refusing to store the Session")
        return False
