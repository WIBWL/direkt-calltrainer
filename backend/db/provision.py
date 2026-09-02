"""Bringing an empty database up to a usable state: migrate, then seed.

Run at application startup and by scripts/seed_reference_data.py, so a fresh
`docker compose up` needs no manual step. Before the Session write of ADR 0034
existed, an unmigrated database was harmless because nothing touched it; now it
silently costs the user their Feedback, so provisioning belongs with the app.

Both halves are idempotent: Alembic skips migrations already applied, and every
seeded record is looked up by its natural key and either created or brought
back to the seed state.

Content sources:
    Persona/Scenario -> backend/db/seed_data.py (ADR 0041: the database is the
                        source of truth and that module carries its initial
                        content; neither is hardcoded in the backend anymore)
    Language         -> the language_id values the seeded Personas use
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

from backend.db.models import Language, MetrikTyp, Persona, PersonaObjection, Scenario
from backend.db.seed_data import LANGUAGE_NAMES, PERSONAS, SCENARIOS
from backend.db.session import session_scope
from backend.feedback.metrics import METRICS

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Every column the ORM requires is carried by seed_data.py, and since the
# library tables were renamed its field names match the columns one to one --
# no mapping happens here anymore. The Feedback tables are the exception and
# keep their German names, so MetrikTyp below still reads `schluessel`.


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
        "Language": _seed_languages(db),
        "Persona": _seed_personas(db),
        "Scenario": _seed_scenarios(db),
        "MetrikTyp": _seed_metrik_typen(db),
    }


def inventory(db: DbSession) -> dict[str, int]:
    """Row counts of the reference tables, for the CLI's summary line."""
    return {
        model.__name__: db.query(model).count()
        for model in (Language, Persona, PersonaObjection, Scenario, MetrikTyp)
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


def _seed_languages(db: DbSession) -> int:
    return sum(
        _upsert(db, Language, {"code": code},
                {"label": LANGUAGE_NAMES.get(code, code)})[1]
        for code in sorted({p["language_id"] for p in PERSONAS})
    )


def _seed_personas(db: DbSession) -> int:
    created = 0
    for p in PERSONAS:
        row, was_created = _upsert(
            db, Persona, {"key": p["id"]},
            {"name": p["name"], "role_label": p["role_label"], "role": p["role"],
             "traits": p["traits"], "behavior": p["behavior"],
             "training_goal": p["training_goal"], "difficulty": p["difficulty"],
             "active": True, "language_code": p["language_id"],
             "tts_voice": p["tts_voice"],
             "kugelaudio_voice_id": p["kugelaudio_voice_id"]})
        created += was_created
        _seed_objections(db, row, p["objections"])
    return created


def _seed_objections(db: DbSession, persona: Persona, objections) -> None:
    """Bring one Persona's objections to the seed state (R-12, ADR 0045).

    Replaced wholesale rather than upserted: the list is what carries meaning,
    and `sort_order` gives a single objection no natural key to match on. Not
    counted as created rows -- `inventory()` already reports the table.
    """
    db.flush()  # a freshly created Persona needs its id before rows point at it
    db.query(PersonaObjection).filter_by(
        persona_id=persona.persona_id).delete(synchronize_session=False)
    for index, text in enumerate(objections):
        db.add(PersonaObjection(persona_id=persona.persona_id, sort_order=index, text=text))


def _seed_scenarios(db: DbSession) -> int:
    return sum(
        _upsert(db, Scenario, {"key": s["id"]},
                {"type": s["type"], "title": s["name"],
                 "short_description": s["short_description"],
                 "description": s["description"], "case_facts": s["case_facts"],
                 "call_goal": s["call_goal"],
                 "success_condition": s["success_condition"]})[1]
        for s in SCENARIOS
    )


def _seed_metrik_typen(db: DbSession) -> int:
    return sum(
        _upsert(db, MetrikTyp, {"schluessel": m.schluessel},
                {"bezeichnung": m.bezeichnung, "einheit": m.einheit,
                 "feature_id": m.feature_id, "aktiv": m.aktiv})[1]
        for m in METRICS
    )
