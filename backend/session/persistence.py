"""Writes a finished Session in one transaction after the call (ADR 0034)."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session as DbSession

from shared.db import models as db_models
from shared.db.session import session_scope
from shared.feedback import interruptions, metrics, rows
from shared.feedback.calls import Conversation, conversation, utterances
from shared.turn import Turn
from backend import consent
from backend.personas import Persona
from backend.scenarios import Scenario

logger = logging.getLogger(__name__)

# A disconnect is stored, but never as completed (ADR 0034).
_STATUS = {
    "user": db_models.STATUS_COMPLETED,
    "completed": db_models.STATUS_COMPLETED,
    "disconnected": db_models.STATUS_ABORTED,
    "error": db_models.STATUS_ABORTED,
}


@dataclass(frozen=True)
class FinishedCall:
    """Named fields: several same-typed strings a positional swap would pass."""

    extern_id: uuid.UUID
    subject_id: str
    persona: Persona
    scenario: Scenario
    turns: Sequence[Turn]
    started_at: datetime
    reason: str


def persist_session(call: FinishedCall) -> int | None:
    """The session_id, or None if consent was refused. The consent check runs
    inside this transaction under `lock_subject` (ADR 0066). Synchronous."""
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
                # Raw facts for the later segment split; the audio is gone (ADR 0081).
                acoustics_json=spoken.acoustics.as_json() if spoken.acoustics else None,
            )
            for index, spoken in enumerate(utterances(turns))
        ]
        _write_analysis(
            db, session, conversation(turns, persona.language_id, scenario.reverse)
        )
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
    """Findings only for hard interruptions: events, not values judged against a threshold."""
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
    """`active` is not checked: a Session may reference a retired row."""
    try:
        ref = uuid.UUID(str(extern_id))
    except (ValueError, TypeError) as e:
        raise LookupError(f"{model.__name__} {extern_id!r} is not a valid id") from e
    row = db.query(model).filter_by(extern_id=ref).one_or_none()
    if row is None:
        raise LookupError(f"{model.__name__} {extern_id!r} is not seeded")
    return row
