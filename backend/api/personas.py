"""REST route for the Persona library (ADR 0041).

`GET /api/personas` feeds the selection screen with display fields only
(ADR 0043) -- the English prompt fields stay on the server.

Personas are curated, not User-authored: unlike Scenarios (ADR 0058), there is
no create/edit here. The `persona` table still carries the authored-content
columns for schema symmetry with `scenario`, but nothing writes them.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend import library
from backend.auth import require_user

router = APIRouter(prefix="/api/personas", dependencies=[Depends(require_user)])


@router.get("")
def list_personas() -> list[dict]:
    """Cards for every selectable Persona.

    `id` on the wire is the `extern_id` (ADR 0050); the client sends it straight
    back in `session.start`. The language comes along because it is the
    Persona's own, not a separate choice (ADR 0043).
    """
    return [
        {
            "id": p.id,
            "name": p.name,
            "role": p.role_label,
            "language": p.language_name,
        }
        for p in library.list_personas()
    ]
