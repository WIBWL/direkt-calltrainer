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

# pylint: disable=duplicate-code
# `_feedback` here and in the sibling route look alike and are not the same: the
# export serves `created_at` and plain points, the detail route `turn_id` and the
# focus goal. Two wire contracts -- merging them would need a flag, and a
# serializer with a flag is worse than two honest ones.


from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session as DbSession

from backend.api._loading import SESSION_SUBTREE
from backend import consent as consent_service
from backend import focus as focus_service
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
            .options(*SESSION_SUBTREE)
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
            # Everything else filed under this subject, and the reason each is
            # here rather than only in the overview: Article 15 is about the
            # personal data, not about the trainings. A settings row, a focus
            # the subject picked and a Scenario they wrote are all stored
            # against their `sub`, and an export that quietly stops at the
            # Sessions is the failure this route's own test warns about.
            "retention": _retention(db, caller.sub),
            "focus": _focus(db, caller.sub),
            "scenarios": _authored_scenarios(db, caller.sub),
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
                # Which stretch of the call this figure describes (ADR 0081).
                # Without it the three rows a metric can have -- whole call,
                # under pressure, the rest -- arrive as three identical keys
                # with different numbers and nothing to tell them apart.
                "segment": m.segment,
                # Included here although the listing drops it (ADR 0064): this
                # is the subject's own copy of their data, so completeness
                # outweighs payload size, which is the opposite trade.
                "detail": m.detail_json,
            }
            for m in session.measurements
        ],
        # One row per event that occurred in the call (F-51), not a judgement
        # against a threshold -- and stored against this Session, so the
        # subject's copy has to carry them.
        "findings": [
            {
                "category": f.category,
                "offset_ms": f.offset_ms,
                "description": f.description,
            }
            for f in sorted(session.findings, key=lambda f: f.offset_ms or 0)
        ],
        "feedback": _feedback(session.feedback),
    }


def _focus(db: DbSession, subject_id: str) -> dict:
    """The training focus the subject picked (F-62).

    A setting rather than training data, which is why no deletion path touches
    it -- and exactly why it has to be in here: nothing else in the export or
    in the profile would tell the subject it is stored at all.
    """
    selection = focus_service.selection(db, subject_id)
    return {
        "decided": selection.decided,
        "decided_at": _iso(selection.decided_at),
        "goals": list(selection.keys),
        "role": selection.role,
        "call_types": list(selection.categories),
    }


def _authored_scenarios(db: DbSession, subject_id: str) -> list[dict]:
    """The Scenarios this subject wrote, including the two kinds derived from
    their own calls (ADR 0058/0069/0070).

    Deactivated rows are included: a Scenario retired from the library is still
    stored under this subject, and an export that showed only the live ones
    would understate what is held. `reverse_brief` comes along because it is
    the one field here written *about* the subject rather than by them -- prose
    a model produced from their own wrap-up.
    """
    rows = (
        db.query(db_models.Scenario)
        .filter_by(created_by=subject_id)
        .order_by(db_models.Scenario.created_at)
        .all()
    )
    return [
        {
            "scenario_id": str(row.extern_id),
            "title": row.title,
            "short_description": row.short_description,
            "description": row.description,
            "case_facts": row.case_facts,
            "call_goal": row.call_goal,
            "briefing": row.briefing,
            "category": row.category,
            "visibility": row.visibility,
            "active": row.active,
            # Which of the three kinds this is, without exposing the internal
            # ids the provenance columns hold.
            "kind": ("reverse" if row.reverse
                     else "follow_up" if row.derived_from_session_id is not None
                     else "authored"),
            "reverse_brief": row.reverse_brief,
            "created_at": _iso(row.created_at),
        }
        for row in rows
    ]


def _feedback(feedback: db_models.Feedback | None) -> dict | None:
    if feedback is None:
        return None
    return {
        "summary": feedback.summary,
        "phase_language": feedback.phase_language,
        "tone_fit": feedback.tone_fit,
        "created_at": feedback.created_at.isoformat(),
        "points": [
            {"kind": p.kind, "text": p.text} for p in feedback.points
        ],
    }
