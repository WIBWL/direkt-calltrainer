"""The Persona and Scenario library, read from the database (ADR 0041).

The one place where the `persona` and `szenario` reference tables are read
and mapped onto the frozen value objects the rest of the backend uses.
Callers get plain dataclasses, so nothing outside this module has to know
about SQLAlchemy sessions, detached instances, or the German column names of
ADR 0026.

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
        id=row.schluessel,
        name=row.name,
        language_id=row.sprache_code,
        language_name=row.sprache.bezeichnung,
        voice=PersonaVoice(
            tts_voice=row.tts_stimme,
            kugelaudio_voice_id=row.kugelaudio_stimme_id,
        ),
        role_label=row.rolle_anzeige,
        role=row.rolle,
        traits=row.haltung,
        behavior=row.verhalten,
        # Sorted here rather than left to the relationship's `order_by`: that
        # only orders what the database returns, so the mapping would depend on
        # how the row was obtained. `reihenfolge` (ADR 0026) is the authored
        # order, and it is the order the prompt gets.
        objections=tuple(
            einwand.text
            for einwand in sorted(row.einwaende, key=lambda e: e.reihenfolge)
        ),
    )


def _to_scenario(row: models.Szenario) -> Scenario:
    return Scenario(
        id=row.schluessel,
        name=row.titel,
        short_description=row.kurzbeschreibung,
        description=row.beschreibung,
        case_facts=row.fallfakten,
        call_goal=row.anrufziel,
        success_condition=row.erfolgsbedingung,
    )


def list_personas() -> list[Persona]:
    """Every selectable Persona, inactive ones left out, ordered by name."""
    with session_scope() as db:
        rows = db.scalars(
            select(models.Persona)
            .options(
                joinedload(models.Persona.sprache),  # language name is part of the mapping
                joinedload(models.Persona.einwaende),  # and so are the objections (ADR 0045)
            )
            .where(models.Persona.aktiv)
            .order_by(models.Persona.name)
        ).unique().all()  # unique(): a joined collection yields one row per objection
        return [_to_persona(row) for row in rows]


def get_persona(persona_id: str) -> Persona | None:
    """The Persona with this key, or None if it doesn't exist or is inactive."""
    with session_scope() as db:
        row = db.scalars(
            select(models.Persona)
            .options(
                joinedload(models.Persona.sprache),
                joinedload(models.Persona.einwaende),
            )
            .where(models.Persona.schluessel == persona_id, models.Persona.aktiv)
        ).unique().one_or_none()
        return _to_persona(row) if row is not None else None


def list_scenarios() -> list[Scenario]:
    """Every selectable Scenario, ordered by title."""
    with session_scope() as db:
        rows = db.scalars(select(models.Szenario).order_by(models.Szenario.titel)).all()
        return [_to_scenario(row) for row in rows]


def get_scenario(scenario_id: str) -> Scenario | None:
    """The Scenario with this key, or None if it doesn't exist."""
    with session_scope() as db:
        row = db.scalar(select(models.Szenario).where(models.Szenario.schluessel == scenario_id))
        return _to_scenario(row) if row is not None else None
