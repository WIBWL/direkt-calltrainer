"""REST route for a finished Session: its Transcript, statistics and Feedback.

The Feedback is generated asynchronously (ADR 0019), so the Session becomes
readable before its wrap-up exists. `status` says which of the two states the
client is looking at, and the client polls until it settles.

Measurements sit next to the Turns rather than inside them: each one describes
the whole call (ADR 0051). What stays per Turn is the Transcript itself, with
the offset that makes it a timestamped Gesprächsprotokoll.

A Session is addressed by its `extern_id`, never by its primary key
(ADR 0050). A valid realm token is required like everywhere else (ADR 0009),
but no owner check is made on top of it: the route is reached from the screen
that just finished the call, and the unguessable id is what keeps one user's
wrap-up out of another's reach. A sequential key would be neither.

The schema is English (ADR 0026), the wire is German: the keys below and the
values of `sprecher` and `art` are what frontend/src/protocol.ts declares and
TranscriptView/FeedbackView compare against, so they are translated back here
rather than changed. This module is the boundary between the two vocabularies.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import selectinload

from backend.auth import require_user
from backend.db import models as db_models
from backend.db.session import session_scope

router = APIRouter(prefix="/api/sessions", dependencies=[Depends(require_user)])

# Schema vocabulary -> wire vocabulary. The inverse of the maps in
# backend/session/persistence.py and backend/feedback/generator.py.
_SPRECHER = {db_models.SPEAKER_USER: "nutzer", db_models.SPEAKER_PERSONA: "persona"}
_PUNKT_ART = {db_models.POINT_STRENGTH: "staerke",
              db_models.POINT_IMPROVEMENT: "verbesserung"}


@router.get("/{extern_id}")
def get_session(extern_id: uuid.UUID) -> dict:
    """One finished Session: Transcript, measurements, Feedback."""
    with session_scope() as db:
        session = (
            db.query(db_models.Session)
            .filter_by(extern_id=extern_id)
            .options(
                selectinload(db_models.Session.turns),
                selectinload(db_models.Session.measurements)
                .selectinload(db_models.Measurement.metric_type),
                selectinload(db_models.Session.feedback)
                .selectinload(db_models.Feedback.points),
                selectinload(db_models.Session.jobs),
                selectinload(db_models.Session.persona),
                selectinload(db_models.Session.scenario),
            )
            .one_or_none()
        )
        if session is None:
            raise HTTPException(status_code=404, detail="Unknown session")
        return {
            "session_id": str(session.extern_id),
            "persona": session.persona.name,
            "szenario": session.scenario.title,
            "status": _feedback_status(session),
            "turns": [_turn(t) for t in sorted(session.turns, key=lambda t: t.seq_index)],
            "messungen": [_messung(m) for m in session.measurements],
            "feedback": _feedback(session.feedback),
        }


def _feedback_status(session: db_models.Session) -> str:
    """queued / running / done / failed, from the newest feedback job (ADR 0032).

    The job row is written in the same transaction as the Session, so its
    absence means nothing will ever generate a wrap-up -- which is "failed"
    from the client's side, and saves it a fifth status to handle.
    """
    jobs = [j for j in session.jobs if j.kind == "feedback"]
    return max(jobs, key=lambda j: j.job_id).status if jobs else "failed"


def _turn(turn: db_models.Turn) -> dict:
    return {
        "turn_id": turn.turn_id,
        "sprecher": _SPRECHER[turn.speaker],
        "start_offset_ms": turn.start_offset_ms,
        "dauer_ms": turn.duration_ms,
        "transkript": turn.transcript,
    }


def _messung(messung: db_models.Measurement) -> dict:
    return {
        "schluessel": messung.metric_type.key,
        "bezeichnung": messung.metric_type.name,
        "einheit": messung.metric_type.unit,
        "wert": float(messung.value),
        "detail": messung.detail_json,
    }


def _feedback(feedback: db_models.Feedback | None) -> dict | None:
    if feedback is None:
        return None
    return {
        "zusammenfassung": feedback.summary,
        "punkte": [
            {"art": _PUNKT_ART[p.kind], "text": p.text, "turn_id": p.turn_id}
            for p in feedback.points
        ],
    }
