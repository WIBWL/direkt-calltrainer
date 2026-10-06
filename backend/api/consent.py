"""Consent routes (ADR 0066); withdrawal deletes in the same transaction."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from shared.db.session import session_scope
from backend import consent as consent_service
from backend import deletion
from backend.auth import AuthContext, require_user

router = APIRouter(prefix="/api/consent", dependencies=[Depends(require_user)])


class Decision(BaseModel):
    """One boolean rather than /grant and /withdraw, so the two cannot drift."""

    granted: bool


@router.get("")
def read_consent(caller: AuthContext = Depends(require_user)) -> dict:
    with session_scope() as db:
        return _state(consent_service.current(db, caller.sub))


@router.post("")
def decide(decision: Decision, caller: AuthContext = Depends(require_user)) -> dict:
    with session_scope() as db:
        # Taken before either write: the write path holds it while reading the
        # decision (ADR 0066).
        consent_service.lock_subject(db, caller.sub)
        state = consent_service.record_decision(db, caller.sub, decision.granted)
        deleted = 0 if decision.granted else deletion.delete_subject_sessions(db, caller.sub)
        return {**_state(state), "deleted_sessions": deleted}


def _state(state: consent_service.ConsentState) -> dict:
    return {
        "status": state.status,
        "version": state.version,
        "decided_at": state.decided_at.isoformat() if state.decided_at else None,
        # The client compares this with `version`.
        "current_version": consent_service.CURRENT_VERSION,
        "allows_storage": state.allows_storage,
        "decision_required": state.decision_required,
    }
