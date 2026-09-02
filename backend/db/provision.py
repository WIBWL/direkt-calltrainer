"""Bringing an empty database up to a usable state: migrate, then seed.

Run at application startup and by scripts/seed_reference_data.py, so a fresh
`docker compose up` needs no manual step. Before the Session write of ADR 0034
existed, an unmigrated database was harmless because nothing touched it; now it
silently costs the user their Feedback, so provisioning belongs with the app.

Both halves are idempotent: Alembic skips migrations already applied, and every
seeded record is looked up by its natural key and either created or brought
back to the seed state.

Content sources:
    Persona/Scenario -> backend/personas.py, backend/scenarios.py
    Language         -> the language_ids the Personas use
    MetricType       -> backend/feedback/metrics.py (METRICS), which also
                        derives the measurement rows, so the seeded inventory
                        and the analysis cannot drift apart.
"""

from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session as DbSession

from backend.db.models import Language, MetricType, Persona, PersonaObjection, Scenario
from backend.db.session import session_scope
from backend.feedback.metrics import METRICS
from backend.personas import PERSONAS
from backend.scenarios import SCENARIOS

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# --- Assumptions ---------------------------------------------------------
# Columns the ORM requires but the hardcoded source modules do not provide:
#
# Persona.difficulty: not modelled in personas.py. "mittel" because
#   the one existing Persona is demanding, but not an escalation case.
# Persona.training_goal: not modelled in personas.py. Left empty rather than
#   invented here — the Personas carry no training goal today.
# Scenario.scenario_type: not modelled in scenarios.py. Derived from F-03
#   ("Angebots- und Preisgespräche"), as the scenario aims at the closing.
# Language.name: personas.py only carries the language code, so the
#   display names live here, for the codes the Personas actually use.
#
# Persona.language_code, tts_voice and kugelaudio_voice_id do come from
# personas.py: each Persona is bound to one language and one voice per TTS
# backend (ADR 0043), and those belong in the table the app reads from
# (ADR 0041) rather than only in the module that seeds it.
DEFAULT_DIFFICULTY = "mittel"
DEFAULT_TRAINING_GOAL = ""
DEFAULT_SCENARIO_TYPE = "Angebots- und Preisgespräch"
LANGUAGE_NAMES = {"de": "Deutsch", "en": "English"}


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
    created = {
        "Language": _seed_languages(db),
        "Persona": _seed_personas(db),
        "Scenario": _seed_scenarios(db),
        "MetricType": _seed_metric_types(db),
    }
    # Deactivate, never delete: `session` references these rows by foreign key,
    # so a Persona dropped from the seed has to stay readable for the Sessions
    # that already ran with it. /api/personas and /api/scenarios filter on
    # `active`, which is what actually removes it from the selection.
    _deactivate_missing(db, Persona, {p.id for p in PERSONAS})
    _deactivate_missing(db, Scenario, {s.id for s in SCENARIOS})
    # Languages are deliberately absent: a closed code list, never retired, and
    # a Session keeps pointing at the code it ran in.
    return created


def _deactivate_missing(db: DbSession, model, seeded_keys: set[str]) -> None:
    """Sets `active` to False on every row the seed no longer contains."""
    (
        db.query(model)
        .filter(model.key.notin_(seeded_keys), model.active.is_(True))
        .update({"active": False}, synchronize_session=False)
    )


def inventory(db: DbSession) -> dict[str, int]:
    """Row counts of the reference tables, for the CLI's summary line."""
    return {
        model.__name__: db.query(model).count()
        for model in (Language, Persona, PersonaObjection, Scenario, MetricType)
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
                {"name": LANGUAGE_NAMES.get(code, code)})[1]
        for code in sorted({p.language_id for p in PERSONAS})
    )


def _seed_personas(db: DbSession) -> int:
    # personas.py no longer models objections, so the seed state for every
    # Persona is "none" and leftovers from earlier runs go. When objections
    # return, the upsert logic for them returns too.
    db.query(PersonaObjection).delete(synchronize_session=False)
    return sum(
        _upsert(db, Persona, {"key": p.id},
                {"name": p.name, "role": p.role, "traits": p.traits,
                 "behavior": p.behavior, "training_goal": DEFAULT_TRAINING_GOAL,
                 "difficulty": DEFAULT_DIFFICULTY,
                 "language_code": p.language_id,
                 "tts_voice": p.voice.tts_voice,
                 "kugelaudio_voice_id": p.voice.kugelaudio_voice_id,
                 "active": True})[1]
        for p in PERSONAS
    )


def _seed_scenarios(db: DbSession) -> int:
    return sum(
        _upsert(db, Scenario, {"key": s.id},
                {"scenario_type": DEFAULT_SCENARIO_TYPE, "title": s.name,
                 "description": s.description, "active": True})[1]
        for s in SCENARIOS
    )


def _seed_metric_types(db: DbSession) -> int:
    return sum(
        _upsert(db, MetricType, {"key": m.schluessel},
                {"name": m.bezeichnung, "unit": m.einheit,
                 "feature_id": m.feature_id, "active": m.aktiv})[1]
        for m in METRICS
    )
