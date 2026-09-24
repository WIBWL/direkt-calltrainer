"""Writing a finished Session to the database (ADR 0034), in one transaction after
the call has ended -- never from the live turn loop, which must not fail on the DB.

Writes the two readings `backend/feedback/calls.py` produces (the utterances on
their timeline and the folded call) as rows."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session as DbSession

# Imported as a module, not by name: `db.Session`/`db.Turn` keep the schema's
# entities visibly distinct from the identically named in-memory ones.
from backend import consent
from backend.db import models as db_models
from backend.db.session import session_scope
from backend.feedback import interruptions, metrics, rows
from backend.feedback.calls import Conversation, conversation, utterances
from backend.personas import Persona
from backend.scenarios import Scenario
from backend.session.models import Turn

logger = logging.getLogger(__name__)

# How a Session ended, in the wire protocol's vocabulary -> in the schema's.
# "disconnected" is a call nobody ended: stored, because the training happened,
# but never as completed -- the history and the activity calendar count a
# finished training, and walking away is not one (ADR 0034's amendment).
_STATUS = {
    "user": db_models.STATUS_COMPLETED,
    "completed": db_models.STATUS_COMPLETED,
    "disconnected": db_models.STATUS_ABORTED,
    "error": db_models.STATUS_ABORTED,
}


@dataclass(frozen=True)
class FinishedCall:
    """Everything the write needs to know about a call that has ended; named
    fields because several are same-typed strings a positional swap would pass."""

    extern_id: uuid.UUID
    # The Keycloak `sub` from the handshake (ADR 0009): the Session belongs to
    # the account that placed the call, not to a placeholder (ADR 0031).
    subject_id: str
    persona: Persona
    scenario: Scenario
    turns: Sequence[Turn]
    started_at: datetime
    # How it ended, in the wire protocol's vocabulary (see `_STATUS`).
    reason: str


def persist_session(call: FinishedCall) -> int | None:
    """Write the Session, its Turns and measurements; the session_id, or None if
    storage consent was refused. The consent check sits *inside* this transaction
    under `lock_subject` (ADR 0066): outside it, a concurrent withdrawal could commit
    in between and strand this Session beyond every deletion path. Synchronous; the
    caller runs it off the event loop after the call (ADR 0034)."""
    extern_id, subject_id, persona, scenario = call.extern_id, call.subject_id, call.persona, call.scenario
    turns = call.turns
    with session_scope() as db:
        consent.lock_subject(db, subject_id)
        if not consent.allows_storage(subject_id, db=db):
            logger.info("Session not stored: no storage consent for this subject")
            return None
        session = db_models.Session(
            extern_id=extern_id,
            subject_id=subject_id,
            persona=_reference(db, db_models.Persona, persona.id),
            scenario=_reference(db, db_models.Scenario, scenario.id),
            language_code=persona.language_id,
            status=_STATUS.get(call.reason, db_models.STATUS_ABORTED),
            started_at=call.started_at,
            ended_at=datetime.now(UTC),
        )
        session.turns = [
            db_models.Turn(
                speaker=spoken.speaker,
                seq_index=index,
                start_offset_ms=spoken.offset_ms,
                duration_ms=spoken.duration_ms,
                transcript=spoken.text,
                interrupted=spoken.interrupted,
                unheard_text=spoken.unheard or None,
                # The raw facts of this utterance, kept because the audio they
                # were measured from is discarded when the call ends (ADR 0048)
                # while which stretch of the call was demanding is decided
                # afterwards, by the wrap-up (ADR 0081). NULL on a Persona row.
                acoustics_json=spoken.acoustics.as_json() if spoken.acoustics else None,
            )
            for index, spoken in enumerate(utterances(turns))
        ]
        _write_analysis(
            db, session, conversation(turns, persona.language_id, scenario.reverse)
        )
        # The wrap-up itself is generated asynchronously (ADR 0018/0019); this
        # row is what makes its outcome queryable afterwards (ADR 0032).
        session.jobs = [db_models.AnalysisJob(
            kind=db_models.JOB_KIND_FEEDBACK,
            status=db_models.JOB_QUEUED,
            attempts=0,
            updated_at=datetime.now(UTC),
        )]
        db.add(session)
        db.flush()
        logger.info("Session persisted: id=%d turns=%d measurements=%d",
                    session.session_id, len(session.turns), len(session.measurements))
        return session.session_id


def _write_analysis(
    db: DbSession, session: db_models.Session, call: Conversation
) -> None:
    """Attach the Session's Measurement and Finding rows (`feedback/rows.py` owns
    dropping unknown metrics and rounding). Findings only for hard interruptions:
    an event at a moment, not a value judged against a threshold, which ADR 0051
    forbids for lack of a norm."""
    ids = rows.metric_ids(db)
    session.measurements = rows.measurements(ids, metrics.measure(call))
    session.findings = [
        db_models.Finding(
            metric_type_id=ids.get(interruptions.COUNT_KEY),
            category=interruptions.FINDING_CATEGORY,
            offset_ms=event.offset_ms,
            description=interruptions.finding_description(event),
        )
        for event in interruptions.classify(call.timeline).hard
    ]


def _reference(db: DbSession, model: type, extern_id: str):
    """The Persona / Scenario row a Session points at, by its `extern_id` (the
    value object's `.id` since ADR 0058). `active` is not checked: a Session may
    reference a since-retired row."""
    try:
        ref = uuid.UUID(str(extern_id))
    except (ValueError, TypeError) as e:
        raise LookupError(f"{model.__name__} {extern_id!r} is not a valid id") from e
    row = db.query(model).filter_by(extern_id=ref).one_or_none()
    if row is None:
        raise LookupError(f"{model.__name__} {extern_id!r} is not seeded")
    return row
