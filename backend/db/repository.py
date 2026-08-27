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
import uuid

from sqlalchemy.orm import Session as DbSession

from backend.db.models import Persona as PersonaRow
from backend.db.models import Session as SessionRow
from backend.db.models import Szenario as SzenarioRow
from backend.db.models import Turn as TurnRow
from backend.personas import Persona, PersonaVoice
from backend.scenarios import Scenario
from backend.session.models import FinishedSession, StoredSession, Turn

# How a Session ended, as reported by the WebSocket layer, mapped onto the
# `session.status` vocabulary. There is no "laufend": the row is written once,
# after the Session is over (ADR 0034).
_STATUS_BY_REASON = {
    "user": "beendet",       # the user hung up
    "completed": "beendet",  # the Persona ended the call
    "error": "abgebrochen",  # a pipeline leg failed past its retry (ADR 0016)
}


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


def find_session(db: DbSession, extern_id: uuid.UUID) -> StoredSession | None:
    """Reads a stored Session back by its public id, Turns included.

    Looked up by `extern_id` and never by the primary key, so nothing the client
    holds can be used to walk to a Session that is not its own. There is
    deliberately no "list all Sessions" counterpart: `subject_id` is a fresh
    pseudonym per Session (ADR 0031), so the server genuinely cannot tell which
    Sessions belong together — only the client that kept the ids can.
    """
    row = (
        db.query(SessionRow)
        .filter(SessionRow.extern_id == extern_id)
        .one_or_none()
    )
    if row is None:
        return None

    turns = (
        db.query(TurnRow)
        .filter(TurnRow.session_id == row.session_id)
        .order_by(TurnRow.seq_index)
        .all()
    )
    return StoredSession(
        extern_id=row.extern_id,
        persona_name=row.persona.name,
        scenario_name=row.szenario.titel,
        status=row.status,
        started_at=row.gestartet_am,
        ended_at=row.beendet_am,
        turns=[
            Turn(
                seq=turn.seq_index,
                persona_text=turn.persona_transkript,
                user_text=turn.nutzer_transkript,
                user_duration_ms=turn.nutzer_dauer_ms,
                persona_duration_ms=turn.persona_dauer_ms,
            )
            for turn in turns
        ],
    )


def save_session(db: DbSession, finished: FinishedSession) -> int:
    """Writes a finished Session and its Turns in one transaction (ADR 0034).

    Called once, after the Session has ended — never during it. Returns the new
    `session_id`.

    Personas and Szenarien are looked up without the `aktiv` filter that
    `find_persona`/`find_scenario` apply: one can be retired while a Session is
    still running, and that Session still has to be recordable against it.
    """
    persona_id = (
        db.query(PersonaRow.persona_id)
        .filter(PersonaRow.schluessel == finished.persona_key)
        .scalar()
    )
    scenario_id = (
        db.query(SzenarioRow.szenario_id)
        .filter(SzenarioRow.schluessel == finished.scenario_key)
        .scalar()
    )
    if persona_id is None or scenario_id is None:
        raise LookupError(
            f"Cannot save Session: unknown persona {finished.persona_key!r} "
            f"or scenario {finished.scenario_key!r}"
        )

    session_row = SessionRow(
        extern_id=finished.extern_id,
        subject_id=finished.subject_id,
        persona_id=persona_id,
        szenario_id=scenario_id,
        sprache_code=finished.language_code,
        status=_STATUS_BY_REASON.get(finished.reason, "abgebrochen"),
        gestartet_am=finished.started_at,
        beendet_am=finished.ended_at,
    )
    db.add(session_row)
    db.flush()  # assigns session_id, which the Turns need

    db.add_all(
        TurnRow(
            session_id=session_row.session_id,
            seq_index=turn.seq,
            nutzer_transkript=turn.user_text,
            persona_transkript=turn.persona_text,
            nutzer_dauer_ms=turn.user_duration_ms,
            persona_dauer_ms=turn.persona_duration_ms,
        )
        # A Turn where both legs failed carries no transcript at all; the fact
        # that it failed is already in the Session's "abgebrochen" status, so an
        # empty row would add nothing.
        for turn in finished.turns
        if turn.user_text or turn.persona_text
    )
    return session_row.session_id
