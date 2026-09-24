"""REST routes for the training focus (F-62, ADR 0076), on the caller's `sub` only.

The catalogue rides along with the selection: the screens never want one
without the other, and two requests could render half a state. PUT, because the
body replaces the whole selection (unlike `/api/consent`, which appends)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend import focus as focus_service
from backend.auth import AuthContext, require_user
from backend.db.session import session_scope

router = APIRouter(prefix="/api/focus", dependencies=[Depends(require_user)])


class FocusChoice(BaseModel):
    """The goals to focus on. An empty list is a real answer — "no focus",
    everything weighted alike — and not the absence of one; what distinguishes
    the two is that this request was made at all (ADR 0076)."""

    goals: list[str] = Field(default_factory=list)
    # What the User said about their work. Sent in full with every request,
    # like the goals: a PUT that leaves them out means "none".
    role: str | None = None
    categories: list[str] = Field(default_factory=list)


@router.get("")
def read_focus(caller: AuthContext = Depends(require_user)) -> dict:
    """The catalogue, the caller's selection, and whether one is still needed."""
    with session_scope() as db:
        return _state(
            focus_service.list_goals(db), focus_service.selection(db, caller.sub)
        )


@router.put("")
def set_focus(choice: FocusChoice, caller: AuthContext = Depends(require_user)) -> dict:
    """Replace the caller's focus.

    A bad request is a 400, never a silent truncation to a focus the user did
    not pick.
    """
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
    # A retired goal stays in the stored selection (that is the point of
    # deactivating rather than deleting) but must not be served: the picker
    # shows no card for it, so it would silently occupy one of the five slots
    # and the user would see four ticks and no sixth box to tick.
    offered = {goal.key for goal in goals}
    return {
        # The limit travels with the payload so the interface enforces the same
        # number the backend does, rather than its own copy of it (ADR 0063).
        "max_goals": focus_service.MAX_GOALS,
        "decided": selection.decided,
        "decided_at": selection.decided_at.isoformat() if selection.decided_at else None,
        "decision_required": selection.decision_required,
        "selected": [key for key in selection.keys if key in offered],
        "role": selection.role,
        "categories": list(selection.categories),
        # The roles on offer, each with the call types it preselects.
        "roles": focus_service.roles(),
        "groups": focus_service.groups(),
        # `evidence` is not on the wire. It says how far a goal can be measured
        # today, which is planning information for the analysis work rather than
        # something a user should have to weigh up while picking (ADR 0076).
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
