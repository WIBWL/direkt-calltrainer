"""What is stored about the caller, and a copy of it (ADR 0066).

Two routes over the same data and they are deliberately not one. The overview
is a handful of counts, cheap enough to load with the profile screen on every
visit; the export is every row the subject owns, which is large, slow and only
ever wanted deliberately. Serving the second where the first was needed would
put a full transcript dump behind an ordinary page load.

Both are scoped by the caller's own `sub` in the query itself, like the history
(ADR 0064): there is no form of either request that is about somebody else, so
there is none to authorise or refuse.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session as DbSession, selectinload

from backend import consent as consent_service
from backend import retention
from backend.auth import AuthContext, require_user
from backend.db import models as db_models
from backend.db.session import session_scope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/me", dependencies=[Depends(require_user)])


@router.get("/data")
def data_overview(caller: AuthContext = Depends(require_user)) -> dict:
    """How much is stored, and over what period.

    Counts rather than content: the point is to let someone see the *extent* of
    what is held about them at a glance, which a list of transcripts does not
    do. The transcripts themselves are one click further on, in the history or
    the export.
    """
    with session_scope() as db:
        sessions = db.query(db_models.Session).filter_by(subject_id=caller.sub)
        session_ids = [row.session_id for row in sessions.with_entities(
            db_models.Session.session_id).all()]

        first, last = (
            db.query(func.min(db_models.Session.started_at),
                     func.max(db_models.Session.started_at))
            .filter(db_models.Session.subject_id == caller.sub)
            .one()
        )

        return {
            "sessions": len(session_ids),
            "utterances": _count(db, db_models.Turn, session_ids),
            "measurements": _count(db, db_models.Measurement, session_ids),
            "feedbacks": _count(db, db_models.Feedback, session_ids),
            "first_session_at": first.isoformat() if first else None,
            "last_session_at": last.isoformat() if last else None,
            "consent": _consent(db, caller.sub),
            "retention": _retention(db, caller.sub),
        }


@router.get("/export")
def export_data(caller: AuthContext = Depends(require_user)) -> JSONResponse:
    """Everything stored about the caller, as one structured JSON document.

    Relationships are kept by nesting rather than by repeating foreign keys: a
    copy of your own data should be readable by you, and a set of flat tables
    joined on integers is not. The internal primary keys stay out of it for the
    same reason — they say nothing to the reader and nothing outside this
    database can use them.

    Served as a download. The browser must not render a page of transcripts
    in a tab that the next person at the machine can page back to.
    """
    with session_scope() as db:
        sessions = (
            db.query(db_models.Session)
            .filter_by(subject_id=caller.sub)
            .options(
                selectinload(db_models.Session.turns),
                selectinload(db_models.Session.measurements)
                .selectinload(db_models.Measurement.metric_type),
                selectinload(db_models.Session.feedback)
                .selectinload(db_models.Feedback.points),
                selectinload(db_models.Session.persona),
                selectinload(db_models.Session.scenario),
            )
            .order_by(db_models.Session.started_at.asc())
            .all()
        )
        document = {
            "exported_at": datetime.now(UTC).isoformat(),
            # Named here because the export is the one place the subject sees
            # the identifier their data is filed under, and ADR 0031's point is
            # that it is a pseudonym rather than an anonymisation.
            "subject_id": caller.sub,
            "consent": _consent(db, caller.sub),
            "sessions": [_session(s) for s in sessions],
        }

    filename = f"calltrainer-export-{datetime.now(UTC).date().isoformat()}.json"
    return JSONResponse(
        content=document,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _count(db: DbSession, model, session_ids: list[int]) -> int:
    """How many rows of `model` belong to these Sessions."""
    if not session_ids:
        # `IN ()` is not valid SQL and SQLAlchemy warns about the empty form.
        return 0
    # count() over the primary key rather than func.count(): pylint cannot see
    # through SQLAlchemy's generic function factory and flags the bare form.
    return db.query(model).filter(model.session_id.in_(session_ids)).count()


class RetentionChoice(BaseModel):
    """Whether the six-month sweep applies to this account (ADR 0067)."""

    auto_delete: bool


@router.post("/retention")
def set_retention(
    choice: RetentionChoice, caller: AuthContext = Depends(require_user)
) -> dict:
    """Switch the automatic deletion on or off for the caller.

    Switching it off does not touch anything already stored, and switching it
    back on does not delete anything on the spot either: the next sweep applies
    the period as it always would. That keeps the setting a statement about the
    future rather than an action with an immediate and surprising effect.
    """
    with session_scope() as db:
        retention.set_auto_delete(db, caller.sub, choice.auto_delete)
        return _retention(db, caller.sub)


def _retention(db: DbSession, subject_id: str) -> dict:
    """The retention setting, and when it next bites."""
    return {
        "auto_delete": retention.auto_delete_enabled(db, subject_id),
        # Days rather than a formatted period: the client says it in its own
        # words, and the number is the fact.
        "retention_days": retention.RETENTION.days,
        # None when nothing is stored, or when the sweep is suspended. The
        # interface must then say nothing about a date, because there is not
        # going to be one.
        "next_expiry_at": _iso(retention.next_expiry(db, subject_id)),
    }


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def _consent(db: DbSession, subject_id: str) -> dict:
    state = consent_service.current(db, subject_id)
    return {
        "status": state.status,
        "version": state.version,
        "decided_at": state.decided_at.isoformat() if state.decided_at else None,
        "allows_storage": state.allows_storage,
    }


def _session(session: db_models.Session) -> dict:
    return {
        "session_id": str(session.extern_id),
        "persona": session.persona.name,
        "scenario": session.scenario.title,
        "language": session.language_code,
        "status": session.status,
        "started_at": session.started_at.isoformat(),
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "transcript": [
            {
                "speaker": t.speaker,
                "start_offset_ms": t.start_offset_ms,
                "duration_ms": t.duration_ms,
                "text": t.transcript,
            }
            for t in sorted(session.turns, key=lambda t: t.seq_index)
        ],
        "measurements": [
            {
                "key": m.metric_type.key,
                "name": m.metric_type.name,
                "unit": m.metric_type.unit,
                "value": float(m.value),
                # Included here although the listing drops it (ADR 0064): this
                # is the subject's own copy of their data, so completeness
                # outweighs payload size, which is the opposite trade.
                "detail": m.detail_json,
            }
            for m in session.measurements
        ],
        "feedback": _feedback(session.feedback),
    }


def _feedback(feedback: db_models.Feedback | None) -> dict | None:
    if feedback is None:
        return None
    return {
        "summary": feedback.summary,
        "phase_language": feedback.phase_language,
        "created_at": feedback.created_at.isoformat(),
        "points": [
            {"kind": p.kind, "text": p.text} for p in feedback.points
        ],
    }
