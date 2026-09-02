"""REST route for a finished Session: its Transcript, statistics and Feedback.

The Feedback is generated asynchronously (ADR 0019), so the Session becomes
readable before its wrap-up exists. `status` says which of the two states the
client is looking at, and the client polls until it settles.

Measurements sit next to the Turns rather than inside them: each one describes
the whole call (ADR 0051). What stays per Turn is the Transcript itself, with
the offset that makes it a timestamped Gesprächsprotokoll.

A Session is addressed by its `oeffentliche_id`, never by its primary key
(ADR 0050). A valid realm token is required like everywhere else (ADR 0009),
but no owner check is made on top of it: the route is reached from the screen
that just finished the call, and the unguessable id is what keeps one user's
wrap-up out of another's reach. A sequential key would be neither.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import selectinload

from backend.auth import require_user
from backend.db import models as db_models
from backend.db.session import session_scope

router = APIRouter(prefix="/api/sessions", dependencies=[Depends(require_user)])


@router.get("/{oeffentliche_id}")
def get_session(oeffentliche_id: uuid.UUID) -> dict:
    """One finished Session: Transcript, measurements, Feedback."""
    with session_scope() as db:
        session = (
            db.query(db_models.Session)
            .filter_by(oeffentliche_id=oeffentliche_id)
            .options(
                selectinload(db_models.Session.turns),
                selectinload(db_models.Session.messungen)
                .selectinload(db_models.Messung.metrik_typ),
                selectinload(db_models.Session.feedback)
                .selectinload(db_models.Feedback.punkte),
                selectinload(db_models.Session.jobs),
                selectinload(db_models.Session.persona),
                selectinload(db_models.Session.szenario),
            )
            .one_or_none()
        )
        if session is None:
            raise HTTPException(status_code=404, detail="Unknown session")
        return {
            "session_id": str(session.oeffentliche_id),
            "persona": session.persona.name,
            "szenario": session.szenario.title,
            "status": _feedback_status(session),
            "turns": [_turn(t) for t in sorted(session.turns, key=lambda t: t.seq_index)],
            "messungen": [_messung(m) for m in session.messungen],
            "feedback": _feedback(session.feedback),
        }


def _feedback_status(session: db_models.Session) -> str:
    """queued / running / done / failed, from the newest feedback job (ADR 0032).

    The job row is written in the same transaction as the Session, so its
    absence means nothing will ever generate a wrap-up -- which is "failed"
    from the client's side, and saves it a fifth status to handle.
    """
    jobs = [j for j in session.jobs if j.art == "feedback"]
    return max(jobs, key=lambda j: j.job_id).status if jobs else "failed"


def _turn(turn: db_models.Turn) -> dict:
    return {
        "turn_id": turn.turn_id,
        "sprecher": turn.sprecher,
        "start_offset_ms": turn.start_offset_ms,
        "dauer_ms": turn.dauer_ms,
        "transkript": turn.transkript,
    }


def _messung(messung: db_models.Messung) -> dict:
    return {
        "schluessel": messung.metrik_typ.schluessel,
        "bezeichnung": messung.metrik_typ.bezeichnung,
        "einheit": messung.metrik_typ.einheit,
        "wert": float(messung.wert),
        "detail": messung.detail_json,
    }


def _feedback(feedback: db_models.Feedback | None) -> dict | None:
    if feedback is None:
        return None
    return {
        "zusammenfassung": feedback.zusammenfassung,
        "punkte": [
            {"art": p.art, "text": p.text, "turn_id": p.turn_id}
            for p in feedback.punkte
        ],
    }
