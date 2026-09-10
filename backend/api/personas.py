"""REST routes for the Persona library (ADR 0041).

`GET /api/personas` feeds the selection screen with display fields only
(ADR 0043) -- the English prompt fields stay on the server.

`GET /api/personas/{id}` is the same rule applied to the info panel behind
a card: it serves the German *display* twins of the prompt fields
(`role_label`, `traits_label`, the objections' `text_label`) and the German
`training_goal`, never `role`, `traits`, `behavior` or an objection's English
`text`. Split off the card route rather than folded into it, the way
`GET /api/scenarios/{id}` is: the list stays a list, and the panel is opened
for one Persona at a time.

Personas are curated, not User-authored: unlike Scenarios (ADR 0058), there is
no create/edit here. The `persona` table still carries the authored-content
columns for schema symmetry with `scenario`, but nothing writes them.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend import library
from backend.auth import require_user

router = APIRouter(prefix="/api/personas", dependencies=[Depends(require_user)])


@router.get("")
def list_personas() -> list[dict]:
    """Cards for every selectable Persona.

    `id` on the wire is the `extern_id` (ADR 0050); the client sends it straight
    back in `session.start`. The language comes along because it is the
    Persona's own, not a separate choice (ADR 0043).

    `avatar_url` is a path into the frontend's own static files, not an
    external URL, and may be null -- the card then shows the Persona's
    initials.
    """
    return [
        {
            "id": p.id,
            "name": p.name,
            "role": p.role_label,
            "language": p.language_name,
            "avatar_url": p.avatar_url,
        }
        for p in library.list_personas()
    ]


@router.get("/{extern_id}")
def get_persona(extern_id: str) -> dict:
    """Everything the info panel shows about one Persona, in German.

    Read-only: Personas are curated, not User-authored (ADR 0058), so there
    is no PATCH beside this. An unknown or inactive id is a 404 -- the same
    answer `library.get_persona` gives for either, since an inactive Persona
    is not on offer.

    `objections` carries the display labels, not the English moves the
    prompt gets. A seeded Persona always has one per objection; the filter
    drops any that is missing rather than showing an empty bullet.
    """
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
