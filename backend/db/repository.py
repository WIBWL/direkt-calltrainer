"""Reads reference data out of the database and hands it to the rest of the
backend as plain domain objects.

The `persona`/`szenario` tables are the source of truth; `backend/personas.py`
and `backend/scenarios.py` only seed them and contribute the dataclasses used
here (ADR 0024 has Users authoring their own, which have to come from the
database). Mapping to those dataclasses at this boundary keeps the API layer
and the SessionOrchestrator free of ORM objects, so neither has to care that
the columns are named in German or that rows can be deactivated.

Every function takes an open session; opening one is the caller's job, because
the caller knows whether it is on the event loop (see session_ws.py) or in
FastAPI's threadpool (see app.py).
"""
from sqlalchemy.orm import Session as DbSession

from backend.db.models import Persona as PersonaRow
from backend.db.models import Szenario as SzenarioRow
from backend.personas import Persona, PersonaVoice
from backend.scenarios import Scenario


def _to_persona(row: PersonaRow) -> Persona:
    return Persona(
        id=row.schluessel,
        name=row.name,
        language_id=row.sprache_code,
        voice=PersonaVoice(
            tts_voice=row.tts_voice,
            kugelaudio_voice_id=row.kugelaudio_voice_id,
        ),
        role=row.rolle,
        traits=row.haltung,
        behavior=row.verhalten,
    )


def _to_scenario(row: SzenarioRow) -> Scenario:
    return Scenario(id=row.schluessel, name=row.titel, description=row.beschreibung)


def list_personas(db: DbSession) -> list[Persona]:
    """The Personas offered for a new Session, deactivated ones excluded."""
    rows = (
        db.query(PersonaRow)
        .filter(PersonaRow.aktiv.is_(True))
        .order_by(PersonaRow.name)
        .all()
    )
    return [_to_persona(row) for row in rows]


def list_scenarios(db: DbSession) -> list[Scenario]:
    """The Scenarios offered for a new Session, deactivated ones excluded."""
    rows = (
        db.query(SzenarioRow)
        .filter(SzenarioRow.aktiv.is_(True))
        .order_by(SzenarioRow.titel)
        .all()
    )
    return [_to_scenario(row) for row in rows]


def find_persona(db: DbSession, schluessel: str) -> Persona | None:
    """Looks up a Persona for a starting Session. Deactivated Personas are not
    found, so a stale client cannot start a Session against a retired one."""
    row = (
        db.query(PersonaRow)
        .filter(PersonaRow.schluessel == schluessel, PersonaRow.aktiv.is_(True))
        .one_or_none()
    )
    return _to_persona(row) if row else None


def find_scenario(db: DbSession, schluessel: str) -> Scenario | None:
    """Looks up a Scenario for a starting Session; see `find_persona`."""
    row = (
        db.query(SzenarioRow)
        .filter(SzenarioRow.schluessel == schluessel, SzenarioRow.aktiv.is_(True))
        .one_or_none()
    )
    return _to_scenario(row) if row else None
