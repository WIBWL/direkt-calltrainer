"""REST routes for the storage consent (ADR 0066).

Two routes: what the caller has decided, and a new decision. Both act on the
caller's own `sub` and take no subject argument — there is no form of this
request that is about somebody else, so there is none to authorise or reject.

Withdrawing deletes. That follows from consent being the only basis this
application has for keeping the data: once it is gone, continued storage cannot
be justified, so the two happen in one transaction rather than leaving the rows
behind for a second action the user might never take.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend import consent as consent_service
from backend import deletion
from backend.auth import AuthContext, require_user
from backend.db.session import session_scope

router = APIRouter(prefix="/api/consent", dependencies=[Depends(require_user)])


class Decision(BaseModel):
    """The body of a decision. A single explicit boolean, deliberately not a
    verb in the path: "granted: false" and "granted: true" are the same kind of
    act, recorded the same way, and splitting them into /grant and /withdraw
    would invite the two to drift apart."""

    granted: bool


@router.get("")
def read_consent(caller: AuthContext = Depends(require_user)) -> dict:
    """The caller's current decision, and whether one is needed."""
    with session_scope() as db:
        return _state(consent_service.current(db, caller.sub))


@router.post("")
def decide(decision: Decision, caller: AuthContext = Depends(require_user)) -> dict:
    """Record a decision. Withdrawal also deletes what was stored under it.

    Both writes share one transaction, so the outcome is either "withdrawn and
    empty" or unchanged — never a withdrawal on record whose data is still
    there, which is the state that would be hardest to notice and worst to be
    in.
    """
    with session_scope() as db:
        state = consent_service.record_decision(db, caller.sub, decision.granted)
        deleted = 0 if decision.granted else deletion.delete_subject_sessions(db, caller.sub)
        return {**_state(state), "deleted_sessions": deleted}


def _state(state: consent_service.ConsentState) -> dict:
    return {
        "status": state.status,
        "version": state.version,
        "decided_at": state.decided_at.isoformat() if state.decided_at else None,
        # The wording currently in force. The client compares it with `version`
        # to know whether what it is showing is what was agreed to.
        "current_version": consent_service.CURRENT_VERSION,
        "allows_storage": state.allows_storage,
        "decision_required": state.decision_required,
    }
