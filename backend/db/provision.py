"""Bringing an empty database up to a usable state: migrate, then seed.

Run at application startup and by scripts/seed_reference_data.py, so a fresh
`docker compose up` needs no manual step. Before the Session write of ADR 0034
existed, an unmigrated database was harmless because nothing touched it; now it
silently costs the user their Feedback, so provisioning belongs with the app.

Both halves are idempotent: Alembic skips migrations already applied, and every
seeded record is looked up by its natural key and either created or brought
back to the seed state.

Content sources:
    Persona/Szenario -> backend/db/seed_data.py (ADR 0041: the database is the
                        source of truth and that module carries its initial
                        content; neither is hardcoded in the backend anymore)
    Sprache          -> the language_id values the seeded Personas use
    MetrikTyp        -> backend/feedback/metrics.py (METRICS), which also
                        derives the Messung rows, so the seeded inventory and
                        the analysis cannot drift apart.
"""

from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session as DbSession

from backend.db.models import MetrikTyp, Persona, PersonaEinwand, Sprache, Szenario
from backend.db.seed_data import LANGUAGE_NAMES, PERSONAS, SCENARIOS
from backend.db.session import session_scope
from backend.feedback.metrics import METRICS

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Every column the ORM requires is carried by seed_data.py, so nothing is
# defaulted here. The only mapping this module still performs is from the
# English field names there onto the German column names of ADR 0026 --
# which goes away once the schema itself is renamed.


def provision() -> dict[str, int]:
    """Migrate to head and seed the reference tables. Returns rows created."""
    logger.info("Migrating database to head...")
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    # Keep our logging setup; see the note in migrations/env.py.
    config.attributes["configure_logging"] = False
    command.upgrade(config, "head")
    with session_scope() as db:
        return seed(db)


def seed(db: DbSession) -> dict[str, int]:
    """Bring the reference tables to the seed state; returns rows created."""
    return {
        "Sprache": _seed_sprachen(db),
        "Persona": _seed_personas(db),
        "Szenario": _seed_szenarien(db),
        "MetrikTyp": _seed_metrik_typen(db),
    }


def inventory(db: DbSession) -> dict[str, int]:
    """Row counts of the reference tables, for the CLI's summary line."""
    return {
        model.__name__: db.query(model).count()
        for model in (Sprache, Persona, PersonaEinwand, Szenario, MetrikTyp)
    }


def _upsert(db: DbSession, model, natural_key: dict, values: dict):
    """Create the record or bring it back to the seed state.

    Returns (object, created).
    """
    obj = db.query(model).filter_by(**natural_key).one_or_none()
    if obj is None:
        obj = model(**natural_key, **values)
        db.add(obj)
        return obj, True
    for field, value in values.items():
        setattr(obj, field, value)
    return obj, False


def _seed_sprachen(db: DbSession) -> int:
    return sum(
        _upsert(db, Sprache, {"sprache_code": code},
                {"bezeichnung": LANGUAGE_NAMES.get(code, code)})[1]
        for code in sorted({p["language_id"] for p in PERSONAS})
    )


def _seed_personas(db: DbSession) -> int:
    created = 0
    for p in PERSONAS:
        row, was_created = _upsert(
            db, Persona, {"schluessel": p["id"]},
            {"name": p["name"], "rolle_anzeige": p["role_label"], "rolle": p["role"],
             "haltung": p["traits"], "verhalten": p["behavior"],
             "trainingsziel": p["training_goal"],
             "schwierigkeitsgrad": p["difficulty"], "aktiv": True,
             "sprache_code": p["language_id"], "tts_stimme": p["tts_voice"],
             "kugelaudio_stimme_id": p["kugelaudio_voice_id"]})
        created += was_created
        _seed_einwaende(db, row, p["objections"])
    return created


def _seed_einwaende(db: DbSession, persona: Persona, objections) -> None:
    """Bring one Persona's objections to the seed state (R-12, ADR 0045).

    Replaced wholesale rather than upserted: the list is what carries meaning,
    and `reihenfolge` gives a single objection no natural key to match on. Not
    counted as created rows -- `inventory()` already reports the table.
    """
    db.flush()  # a freshly created Persona needs its id before rows point at it
    db.query(PersonaEinwand).filter_by(
        persona_id=persona.persona_id).delete(synchronize_session=False)
    for index, text in enumerate(objections):
        db.add(PersonaEinwand(persona_id=persona.persona_id, reihenfolge=index, text=text))


def _seed_szenarien(db: DbSession) -> int:
    return sum(
        _upsert(db, Szenario, {"schluessel": s["id"]},
                {"typ": s["type"], "titel": s["name"],
                 "kurzbeschreibung": s["short_description"],
                 "beschreibung": s["description"], "fallfakten": s["case_facts"],
                 "anrufziel": s["call_goal"],
                 "erfolgsbedingung": s["success_condition"]})[1]
        for s in SCENARIOS
    )


def _seed_metrik_typen(db: DbSession) -> int:
    return sum(
        _upsert(db, MetrikTyp, {"schluessel": m.schluessel},
                {"bezeichnung": m.bezeichnung, "einheit": m.einheit,
                 "feature_id": m.feature_id, "aktiv": m.aktiv})[1]
        for m in METRICS
    )
