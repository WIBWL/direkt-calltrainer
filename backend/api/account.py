"""What is stored about the caller, and a copy of it (ADR 0066).

Deliberately two routes: the overview is cheap counts loaded with the profile
screen, the export is every row the subject owns and only wanted deliberately.
Both are scoped by the caller's `sub` in the query itself (ADR 0064)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session as DbSession

from backend.api import served
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
    """How much is stored, and over what period: the extent, not the content."""
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
    """Everything stored about the caller, as one nested JSON document.

    Nested rather than flat tables, and without internal primary keys, so the
    subject can read it. Served as a download so a page of transcripts is not
    left in a browser tab."""
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
            # Article 15 covers all personal data, not only the trainings:
            # settings, focus and authored Scenarios are stored against the
            # `sub` too, and an export stopping at the Sessions is incomplete.
            "retention": _retention(db, caller.sub),
            "focus": _focus(db, caller.sub),
            "scenarios": _authored_scenarios(db, caller.sub),
            "sessions": [served.export(s) for s in sessions],
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

    Neither direction acts on the spot: the next sweep applies the period, so
    the setting stays a statement about the future, not a delete button.
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


def _focus(db: DbSession, subject_id: str) -> dict:
    """The training focus the subject picked (F-62).

    A setting no deletion path touches, which is why the export must show it.
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

    Deactivated rows count: they are still stored. `reverse_brief` is included
    as prose a model wrote *about* the subject from their own wrap-up."""
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
