"""The Persona and Scenario library, read from the database (ADR 0041).

The one place where the `persona` and `scenario` reference tables are read
and mapped onto the frozen value objects the rest of the backend uses.
Callers get plain dataclasses, so nothing outside this module has to know
about SQLAlchemy sessions or detached instances.

Deliberately uncached: an edited Persona or Scenario takes effect on the next
Session, which is the whole point of loading them from the database.
"""
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from backend.db import models
from backend.db.session import session_scope
from backend.personas import Persona, PersonaVoice
from backend.scenarios import Scenario


def _to_persona(row: models.Persona) -> Persona:
    return Persona(
        id=row.key,
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
        id=row.key,
        name=row.title,
        short_description=row.short_description,
        description=row.description,
        case_facts=row.case_facts,
        call_goal=row.call_goal,
        success_condition=row.success_condition,
    )


def list_personas() -> list[Persona]:
    """Every selectable Persona, inactive ones left out, ordered by name."""
    with session_scope() as db:
        rows = db.scalars(
            select(models.Persona)
            .options(
                joinedload(models.Persona.language),  # language name is part of the mapping
                joinedload(models.Persona.objections),  # and so are the objections (ADR 0045)
            )
            .where(models.Persona.active)
            .order_by(models.Persona.name)
        ).unique().all()  # unique(): a joined collection yields one row per objection
        return [_to_persona(row) for row in rows]


def get_persona(persona_id: str) -> Persona | None:
    """The Persona with this key, or None if it doesn't exist or is inactive."""
    with session_scope() as db:
        row = db.scalars(
            select(models.Persona)
            .options(
                joinedload(models.Persona.language),
                joinedload(models.Persona.objections),
            )
            .where(models.Persona.key == persona_id, models.Persona.active)
        ).unique().one_or_none()
        return _to_persona(row) if row is not None else None


def list_scenarios() -> list[Scenario]:
    """Every selectable Scenario, ordered by title."""
    with session_scope() as db:
        rows = db.scalars(select(models.Scenario).order_by(models.Scenario.title)).all()
        return [_to_scenario(row) for row in rows]


def get_scenario(scenario_id: str) -> Scenario | None:
    """The Scenario with this key, or None if it doesn't exist."""
    with session_scope() as db:
        row = db.scalar(select(models.Scenario).where(models.Scenario.key == scenario_id))
        return _to_scenario(row) if row is not None else None
