"""Data overview and export (ADR 0066), scoped by `sub` in the query."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session as DbSession

from shared.db import models as db_models
from shared.db.session import session_scope
from backend.api import served
from backend.api._loading import SESSION_SUBTREE
from backend import consent as consent_service
from backend import focus as focus_service
from backend import retention
from backend.auth import AuthContext, require_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/me", dependencies=[Depends(require_user)])


@router.get("/data")
def data_overview(caller: AuthContext = Depends(require_user)) -> dict:
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
    """Nested, without internal keys, served as a download."""
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
            "subject_id": caller.sub,
            "consent": _consent(db, caller.sub),
            # Everything stored against the `sub`, not only the trainings (Art. 15).
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
    if not session_ids:
        return 0
    # count() rather than func.count(): pylint cannot see through the latter.
    return db.query(model).filter(model.session_id.in_(session_ids)).count()


class RetentionChoice(BaseModel):
    auto_delete: bool


@router.post("/retention")
def set_retention(
    choice: RetentionChoice, caller: AuthContext = Depends(require_user)
) -> dict:
    """Takes effect at the next sweep, never on the spot."""
    with session_scope() as db:
        retention.set_auto_delete(db, caller.sub, choice.auto_delete)
        return _retention(db, caller.sub)


def _retention(db: DbSession, subject_id: str) -> dict:
    return {
        "auto_delete": retention.auto_delete_enabled(db, subject_id),
        "retention_days": retention.RETENTION.days,
        # None when nothing is stored or the sweep is suspended.
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
    """A setting no deletion touches, so the export must show it."""
    selection = focus_service.selection(db, subject_id)
    return {
        "decided": selection.decided,
        "decided_at": _iso(selection.decided_at),
        "goals": list(selection.keys),
        "role": selection.role,
        "call_types": list(selection.categories),
    }


def _authored_scenarios(db: DbSession, subject_id: str) -> list[dict]:
    """Including follow-ups and reverses; deactivated rows count, they are still stored."""
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
            "kind": ("reverse" if row.reverse
                     else "follow_up" if row.derived_from_session_id is not None
                     else "authored"),
            "reverse_brief": row.reverse_brief,
            "created_at": _iso(row.created_at),
        }
        for row in rows
    ]
