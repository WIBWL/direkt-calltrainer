"""REST routes for the training focus (F-61, ADR 0074).

Two routes over one thing: what the caller could focus on and what they
currently do, and a replacement for the second. Both act on the caller's own
`sub` and take no subject argument — there is no form of this request that is
about somebody else, so there is none to authorise or reject (ADR 0031/0064).

The catalogue rides along with the selection instead of getting a route of its
own. The two are never wanted apart: the first-run dialog needs the catalogue
*and* whether the question was already answered, and the profile section needs
the catalogue *and* what is ticked. Two routes would mean two round trips and
two chances for the screen to render half a state.

PUT, not POST: the body is the whole selection, so sending it twice leaves the
same five goals rather than ten. That is the difference from `/api/consent`,
which appends decisions and therefore posts.
"""

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
    the two is that this request was made at all (ADR 0074)."""

    goals: list[str] = Field(default_factory=list)


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

    A bad request is a 400 and never a silent truncation: storing the first five
    of six goals would file a focus the user did not pick, and they would have
    no way of telling from the screen that it happened.
    """
    with session_scope() as db:
        try:
            selection = focus_service.set_selection(db, caller.sub, choice.goals)
        except (focus_service.TooManyGoals, focus_service.UnknownGoal) as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return _state(focus_service.list_goals(db), selection)


def _state(
    goals: list[focus_service.Goal], selection: focus_service.Selection
) -> dict:
    return {
        # The limit travels with the payload so the interface enforces the same
        # number the backend does, rather than its own copy of it (ADR 0063).
        "max_goals": focus_service.MAX_GOALS,
        "decided": selection.decided,
        "decided_at": selection.decided_at.isoformat() if selection.decided_at else None,
        "decision_required": selection.decision_required,
        "selected": list(selection.keys),
        "groups": focus_service.groups(),
        # `evidence` is not on the wire. It says how far a goal can be measured
        # today, which is planning information for the analysis work rather than
        # something a user should have to weigh up while picking (ADR 0074).
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
