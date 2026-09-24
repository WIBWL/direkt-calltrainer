"""REST routes for the Persona library (ADR 0041), read-only (ADR 0058).

Both routes serve display fields only, the German twins on the info panel;
the English prompt fields stay on the server (ADR 0043).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend import library
from backend.auth import require_user

router = APIRouter(prefix="/api/personas", dependencies=[Depends(require_user)])


@router.get("")
def list_personas() -> list[dict]:
    """Cards for every selectable Persona.

    `id` is the `extern_id` (ADR 0050), sent back in `session.start`.
    `avatar_url` is a path into the frontend's static files, or null (the card
    then shows initials)."""
    return [
        {
            "id": p.id,
            "name": p.name,
            "role": p.role_label,
            "language": p.language_name,
            # The code as well as the name: the card puts a flag beside the
            # Persona, and picking one off a display string ("Deutsch") would
            # break the first time that string is reworded. Not a prompt field,
            # so ADR 0043 has nothing to say about it.
            "language_code": p.language_id,
            "avatar_url": p.avatar_url,
        }
        for p in library.list_personas()
    ]


@router.get("/{extern_id}")
def get_persona(extern_id: str) -> dict:
    """Everything the info panel shows about one Persona, in German.

    An unknown or inactive id is a 404. `objections` carries the display
    labels, not the English moves the prompt gets; a missing label is dropped
    rather than shown as an empty bullet."""
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
