"""Whether a subject has agreed to their trainings being stored (ADR 0066).

The single place that answers that question. Two callers matter and they are
very different: the REST layer asks so the interface can prompt, and the write
path asks so it can decline — the second one is the one that has to be right,
because it is the last point at which unconsented data can still be prevented
from existing.

Consent is recorded as decisions, never as a current-state row that gets
overwritten. `record_decision` appends, `current` reads the newest. That makes
the history of a subject's decisions readable, which is the point of keeping
them at all, and it makes a withdrawal impossible to confuse with never having
agreed.
"""
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
        """True only for a live `granted` against the *current* wording.

        The version check is the part worth stating: a subject who agreed to an
        older notice has not agreed to this one, and their Sessions must not be
        stored on the strength of a decision about different text.
        """
        return self.status == db_models.CONSENT_GRANTED and self.version == CURRENT_VERSION

    @property
    def decision_required(self) -> bool:
        """True when the interface has to ask before training can be stored.

        Both a missing decision and a stale one require asking. A withdrawal
        does not: it is a decision, and re-prompting someone who just said no
        would make the dialog a way of wearing them down.
        """
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

    Idempotent in the sense that matters: repeating a decision that is already
    in force against the current wording writes nothing, so a double-clicked
    button does not fill the log with identical rows. A decision that *changes*
    something is always written, including a re-grant after a withdrawal.
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

    Both sides of ADR 0066's promise take this before they act: the write path
    before it reads the decision, and `POST /api/consent` before it records a
    withdrawal and deletes what that withdrawal covers. Without it the two
    transactions interleave -- the write reads "granted", the withdrawal
    commits and deletes every Session that exists *at that moment*, then the
    write inserts one more. The result is a stored training under a withdrawn
    consent that no deletion path will ever visit again, which is precisely the
    state ADR 0066 says must not occur.

    Transaction-scoped (`pg_advisory_xact_lock`), so it is released by the
    commit or rollback that ends the caller's transaction and cannot be leaked.
    Keyed on the subject, so two different Users never wait on each other.
    """
    key = int.from_bytes(
        hashlib.blake2b(subject_id.encode("utf-8"), digest_size=8).digest(),
        "big", signed=True,
    )
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


def allows_storage(subject_id: str, db: DbSession | None = None) -> bool:
    """Whether this subject's finished Sessions may be written.

    With `db`, the question is answered inside the caller's own transaction,
    which is how the write path asks: the answer and the INSERT it authorises
    then commit together, and `lock_subject` keeps a withdrawal from slipping
    between them. A failure propagates there rather than being swallowed, and
    that is still failing closed -- it aborts the transaction, so nothing is
    written.

    Without `db` it opens its own transaction, which is what the REST layer
    wants. **Fails closed**: if the question cannot be answered, the answer is
    no. Everywhere else in this application a database failure is logged and
    stepped over, on the grounds that losing a wrap-up is better than losing a
    call — here the same reflex would store data on a guess, which is the one
    outcome consent exists to prevent.
    """
    if db is not None:
        return current(db, subject_id).allows_storage
    try:
        with session_scope() as own:
            return current(own, subject_id).allows_storage
    except Exception:  # pylint: disable=broad-except
        logger.exception("Consent could not be read; refusing to store the Session")
        return False
