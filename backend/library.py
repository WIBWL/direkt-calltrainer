"""The Persona and Scenario library, read from the database (ADR 0041).

The one place where the `persona` and `scenario` reference tables are read,
written and mapped onto the frozen value objects the rest of the backend uses.
Callers get plain dataclasses, so nothing outside this module has to know about
SQLAlchemy sessions or detached instances.

Since ADR 0058 the `scenario` table also holds User-authored rows, so every read
is scoped to the caller (`subject`) and, since ADR 0060, their company
(`tenant_id`, resolved in `backend/tenants.py`): a row is visible if it is
`public` (every shipped built-in), shared with the caller's tenant, or authored
by the caller. The client addresses a row by its `extern_id` (ADR 0050), never
by the internal id or the `key` slug, which an authored row does not have.
Authored text is run through `backend.authored_text.clean` on the way in
(ADR 0059).

Deliberately uncached: an edited Persona or Scenario takes effect on the next
Session, which is the whole point of loading them from the database.
"""
from __future__ import annotations

import uuid

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import joinedload

from backend.authored_text import clean
from backend.db import models
from backend.db.session import session_scope
from backend.personas import Persona, PersonaVoice
from backend.scenarios import Scenario

# Fields an authoring caller may set on a Scenario. `description` and the three
# case fields are prompt input (ADR 0045); `title` / `short_description` are the
# card. Everything else on the row (ids, ownership, `active`) is set here.
_SCENARIO_FIELDS = (
    "title", "short_description",
    "description", "case_facts", "call_goal", "success_condition",
)


def _to_persona(row: models.Persona) -> Persona:
    return Persona(
        id=str(row.extern_id),
        name=row.name,
        language_id=row.language_code,
        language_name=row.language.name,
        voice=PersonaVoice(
            tts_voice=row.tts_voice,
            kugelaudio_voice_id=row.kugelaudio_voice_id,
        ),
        role_label=row.role_label,
        role=row.role,
        traits=row.traits,
        behavior=row.behavior,
        # Sorted here rather than left to the relationship's `order_by`: that
        # only orders what the database returns, so the mapping would depend on
        # how the row was obtained. `position` (ADR 0026) is the authored
        # order, and it is the order the prompt gets.
        objections=tuple(
            objection.text
            for objection in sorted(row.objections, key=lambda e: e.position)
        ),
    )


def _to_scenario(row: models.Scenario) -> Scenario:
    return Scenario(
        id=str(row.extern_id),
        name=row.title,
        short_description=row.short_description,
        description=row.description,
        case_facts=row.case_facts,
        call_goal=row.call_goal,
        success_condition=row.success_condition,
        created_by=row.created_by,
        visibility=row.visibility,
    )


def _visible_to(model, subject: str, tenant_id: int):
    """The WHERE clause for the library a caller may see (ADR 0058, extended by
    ADR 0060): public rows, rows shared with the caller's tenant, and the
    caller's own. Never trusts a value from the client — `subject` and
    `tenant_id` are both derived server-side from the verified token."""
    return or_(
        model.visibility == models.VISIBILITY_PUBLIC,
        and_(
            model.visibility == models.VISIBILITY_TENANT,
            model.tenant_id == tenant_id,
        ),
        model.created_by == subject,
    )


def _as_extern_id(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


# Visibility values a User may set on their own row: not `public` (that needs
# review, ADR 0060 phase 3).
_USER_SETTABLE_VISIBILITY = (models.VISIBILITY_PRIVATE, models.VISIBILITY_TENANT)


def _shareable_ref(extern_id: str, visibility: str) -> uuid.UUID | None:
    """The parsed extern_id, or None if the requested visibility is one a User
    may not set themselves or the id is malformed."""
    if visibility not in _USER_SETTABLE_VISIBILITY:
        return None
    return _as_extern_id(extern_id)


# --- Personas ---------------------------------------------------------------
#
# Personas are curated, not User-authored (unlike Scenarios): there is no
# create/edit here, and no visibility scoping -- every selectable Persona is a
# public built-in.


def list_personas() -> list[Persona]:
    """Every selectable Persona, inactive ones left out, ordered by name."""
    with session_scope() as db:
        rows = db.scalars(
            select(models.Persona)
            .options(
                joinedload(models.Persona.language),
                joinedload(models.Persona.objections),
            )
            .where(models.Persona.active)
            .order_by(models.Persona.name)
        ).unique().all()  # unique(): a joined collection yields one row per objection
        return [_to_persona(row) for row in rows]


def get_persona(extern_id: str) -> Persona | None:
    """The Persona with this `extern_id`, or None if it does not exist or is
    inactive."""
    ref = _as_extern_id(extern_id)
    if ref is None:
        return None
    with session_scope() as db:
        row = db.scalars(
            select(models.Persona)
            .options(
                joinedload(models.Persona.language),
                joinedload(models.Persona.objections),
            )
            .where(models.Persona.extern_id == ref, models.Persona.active)
        ).unique().one_or_none()
        return _to_persona(row) if row is not None else None


# --- Scenarios -------------------------------------------------------------


def list_scenarios(subject: str, tenant_id: int) -> list[Scenario]:
    """Every Scenario this caller may select, ordered by title."""
    with session_scope() as db:
        rows = db.scalars(
            select(models.Scenario)
            .where(
                models.Scenario.active,
                _visible_to(models.Scenario, subject, tenant_id),
            )
            .order_by(models.Scenario.title)
        ).all()
        return [_to_scenario(row) for row in rows]


def get_scenario(extern_id: str, subject: str, tenant_id: int) -> Scenario | None:
    """The Scenario with this `extern_id`, or None — see `get_persona`."""
    ref = _as_extern_id(extern_id)
    if ref is None:
        return None
    with session_scope() as db:
        row = db.scalars(
            select(models.Scenario).where(
                models.Scenario.extern_id == ref,
                models.Scenario.active,
                _visible_to(models.Scenario, subject, tenant_id),
            )
        ).one_or_none()
        return _to_scenario(row) if row is not None else None


def create_scenario(data: dict, subject: str, tenant_id: int) -> Scenario:
    """Author a private Scenario (ADR 0058), stamped with the caller's tenant so
    sharing is later a `visibility` flip (ADR 0060)."""
    with session_scope() as db:
        row = models.Scenario(
            created_by=subject,
            tenant_id=tenant_id,
            visibility=models.VISIBILITY_PRIVATE,
            active=True,
            **_sanitised(data, _SCENARIO_FIELDS),
        )
        db.add(row)
        db.flush()
        db.refresh(row)
        return _to_scenario(row)


def update_scenario(extern_id: str, data: dict, subject: str) -> Scenario | None:
    """Edit a Scenario the caller authored. None if it is not theirs."""
    ref = _as_extern_id(extern_id)
    if ref is None:
        return None
    with session_scope() as db:
        row = db.scalars(
            select(models.Scenario).where(
                models.Scenario.extern_id == ref,
                models.Scenario.created_by == subject,
            )
        ).one_or_none()
        if row is None:
            return None
        for field, value in _sanitised(data, _SCENARIO_FIELDS).items():
            setattr(row, field, value)
        db.flush()
        db.refresh(row)
        return _to_scenario(row)


def deactivate_scenario(extern_id: str, subject: str) -> bool:
    """Retire a Scenario the caller authored (soft)."""
    return _deactivate(models.Scenario, extern_id, subject)


def set_scenario_visibility(
    extern_id: str, visibility: str, subject: str, tenant_id: int
) -> Scenario | None:
    """Share the caller's Scenario with their tenant, or make it private again
    (ADR 0060). Only `private` <-> `tenant`. None if the row is not theirs.

    A row that somehow has no `tenant_id` (created before tenant stamping) is
    stamped with the caller's tenant here, so sharing still works."""
    ref = _shareable_ref(extern_id, visibility)
    if ref is None:
        return None
    with session_scope() as db:
        row = db.scalars(
            select(models.Scenario).where(
                models.Scenario.extern_id == ref,
                models.Scenario.created_by == subject,
            )
        ).one_or_none()
        if row is None:
            return None
        if row.tenant_id is None:
            row.tenant_id = tenant_id
        row.visibility = visibility
        db.flush()
        return _to_scenario(row)


# --- shared helpers -------------------------------------------------------


def _sanitised(data: dict, fields: tuple[str, ...]) -> dict:
    """Pick the authorable fields out of `data` and run the string ones through
    `clean` (ADR 0059). A field the caller omitted is left out, so the same
    helper serves create (all fields) and a partial update."""
    out = {}
    for field in fields:
        if field not in data or data[field] is None:
            continue
        value = data[field]
        out[field] = clean(value) if isinstance(value, str) else value
    return out


def _deactivate(model, extern_id: str, subject: str) -> bool:
    ref = _as_extern_id(extern_id)
    if ref is None:
        return False
    with session_scope() as db:
        row = db.scalars(
            select(model).where(
                model.extern_id == ref, model.created_by == subject
            )
        ).one_or_none()
        if row is None:
            return False
        row.active = False
        return True
