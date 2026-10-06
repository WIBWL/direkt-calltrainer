"""Persona routes, read-only, display fields only (ADR 0043, 0058)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend import library
from backend.auth import require_user

router = APIRouter(prefix="/api/personas", dependencies=[Depends(require_user)])


@router.get("")
def list_personas() -> list[dict]:
    """`avatar_url` is null when there is no portrait (initials then)."""
    return [
        {
            "id": p.id,
            "name": p.name,
            "role": p.role_label,
            "language": p.language_name,
            # The code too: the flag must not be keyed on a display string.
            "language_code": p.language_id,
            "avatar_url": p.avatar_url,
        }
        for p in library.list_personas()
    ]


@router.get("/{extern_id}")
def get_persona(extern_id: str) -> dict:
    """The info panel's German fields; empty objection labels are dropped."""
    persona = library.get_persona(extern_id)
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    return {
        "id": persona.id,
        "name": persona.name,
        "role": persona.role_label,
        "language": persona.language_name,
        "avatar_url": persona.avatar_url,
        "traits": persona.traits_label,
        "training_goal": persona.training_goal,
        "objections": [label for label in persona.objection_labels if label],
    }
