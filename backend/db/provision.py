"""Bringing an empty database up to a usable state: migrate, then seed.

Run at application startup and by scripts/seed_reference_data.py, so a fresh
`docker compose up` needs no manual step. Before the Session write of ADR 0034
existed, an unmigrated database was harmless because nothing touched it; now it
silently costs the user their Feedback, so provisioning belongs with the app.

Both halves are idempotent: Alembic skips migrations already applied, and every
seeded record is looked up by its natural key and either created or brought
back to the seed state.

Content sources:
    Persona/Szenario -> backend/personas.py, backend/scenarios.py
    Sprache          -> the language_ids the Personas use
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
from backend.db.session import session_scope
from backend.feedback.metrics import METRICS
from backend.personas import PERSONAS
from backend.scenarios import SCENARIOS

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# --- Assumptions ---------------------------------------------------------
# Columns the ORM requires but the hardcoded source modules do not provide:
#
# Persona.schwierigkeitsgrad: not modelled in personas.py. "mittel" because
#   the one existing Persona is demanding, but not an escalation case.
# Persona.trainingsziel: not modelled in personas.py. Left empty rather than
#   invented here — the Personas carry no training goal today.
# Szenario.typ: not modelled in scenarios.py. Derived from F-03 ("Angebots-
#   und Preisgespräche"), as the scenario aims at the closing.
# Sprache.bezeichnung: personas.py only carries the language code, so the
#   display names live here, for the codes the Personas actually use.
DEFAULT_SCHWIERIGKEITSGRAD = "mittel"
DEFAULT_TRAININGSZIEL = ""
DEFAULT_SZENARIO_TYP = "Angebots- und Preisgespräch"
SPRACH_BEZEICHNUNGEN = {"de": "Deutsch", "en": "English"}


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
                {"bezeichnung": SPRACH_BEZEICHNUNGEN.get(code, code)})[1]
        for code in sorted({p.language_id for p in PERSONAS})
    )


def _seed_personas(db: DbSession) -> int:
    # personas.py no longer models objections, so the seed state for every
    # Persona is "none" and leftovers from earlier runs go. When objections
    # return, the upsert logic for them returns too.
    db.query(PersonaEinwand).delete(synchronize_session=False)
    return sum(
        _upsert(db, Persona, {"schluessel": p.id},
                {"name": p.name, "rolle": p.role, "haltung": p.traits,
                 "verhalten": p.behavior, "trainingsziel": DEFAULT_TRAININGSZIEL,
                 "schwierigkeitsgrad": DEFAULT_SCHWIERIGKEITSGRAD, "aktiv": True})[1]
        for p in PERSONAS
    )


def _seed_szenarien(db: DbSession) -> int:
    return sum(
        _upsert(db, Szenario, {"schluessel": s.id},
                {"typ": DEFAULT_SZENARIO_TYP, "titel": s.name, "beschreibung": s.description})[1]
        for s in SCENARIOS
    )


def _seed_metrik_typen(db: DbSession) -> int:
    return sum(
        _upsert(db, MetrikTyp, {"schluessel": m.schluessel},
                {"bezeichnung": m.bezeichnung, "einheit": m.einheit,
                 "feature_id": m.feature_id, "aktiv": m.aktiv})[1]
        for m in METRICS
    )
