"""Focus routes (F-62, ADR 0076). PUT replaces the whole selection."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shared.db.session import session_scope
from backend import focus as focus_service
from backend.auth import AuthContext, require_user

router = APIRouter(prefix="/api/focus", dependencies=[Depends(require_user)])


class FocusChoice(BaseModel):
    """An empty list is a real answer: "no focus"."""

    goals: list[str] = Field(default_factory=list)
    # Sent in full each time; omitted means none.
    role: str | None = None
    categories: list[str] = Field(default_factory=list)


@router.get("")
def read_focus(caller: AuthContext = Depends(require_user)) -> dict:
    with session_scope() as db:
        return _state(
            focus_service.list_goals(db), focus_service.selection(db, caller.sub)
        )


@router.put("")
def set_focus(choice: FocusChoice, caller: AuthContext = Depends(require_user)) -> dict:
    """A bad request is a 400, never a silent truncation."""
    with session_scope() as db:
        try:
            selection = focus_service.set_selection(
                db, caller.sub, choice.goals, choice.role, choice.categories
            )
        except (
            focus_service.TooManyGoals, focus_service.UnknownGoal, focus_service.UnknownChoice,
        ) as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return _state(focus_service.list_goals(db), selection)


def _state(
    goals: list[focus_service.Goal], selection: focus_service.Selection
) -> dict:
    # A retired goal stays stored but is not served, or it would silently hold
    # one of the five slots.
    offered = {goal.key for goal in goals}
    return {
        # Served, so the client enforces the backend's number (ADR 0063).
        "max_goals": focus_service.MAX_GOALS,
        "decided": selection.decided,
        "decided_at": selection.decided_at.isoformat() if selection.decided_at else None,
        "decision_required": selection.decision_required,
        "selected": [key for key in selection.keys if key in offered],
        "role": selection.role,
        "categories": list(selection.categories),
        "roles": focus_service.roles(),
        "groups": focus_service.groups(),
        # `evidence` is deliberately not on the wire (ADR 0076).
        "goals": [
            {
                "key": goal.key,
                "title": goal.title,
                "caption": goal.caption,
                "info": goal.info,
                "group": goal.group,
            }
            for goal in goals
        ],
    }
