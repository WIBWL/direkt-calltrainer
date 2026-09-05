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

from backend.authored_text import clean
from backend.db.models import (
    Language,
    MetricType,
    Persona,
    PersonaObjection,
    Scenario,
    Tenant,
    VISIBILITY_PUBLIC,
)
from backend.db.seed_data import LANGUAGE_NAMES, PERSONAS, SCENARIOS, TENANTS
from backend.db.session import session_scope
from backend.feedback.metrics import METRICS

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Every column the ORM requires is carried by seed_data.py, and its field names
# match the columns one to one, so nothing is defaulted or mapped here.


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
        "Tenant": _seed_tenants(db),
        "Persona": _seed_personas(db),
        "Scenario": _seed_scenarios(db),
        "MetricType": _seed_metric_types(db),
    }
    # Deactivate, never delete: `session` references these rows by foreign key,
    # so a Persona dropped from the seed has to stay readable for the Sessions
    # that already ran with it. /api/personas and /api/scenarios filter on
    # `active`, which is what actually removes it from the selection.
    _deactivate_missing(db, Persona, {p["id"] for p in PERSONAS})
    _deactivate_missing(db, Scenario, {s["id"] for s in SCENARIOS})
    # Languages are deliberately absent: a closed code list, never retired, and
    # a Session keeps pointing at the code it ran in.
    return created


def _seed_tenants(db: DbSession) -> int:
    """The pilot companies plus the `default` tenant (ADR 0060). Never
    deactivated -- an authored row keeps pointing at the tenant it belonged to."""
    return sum(
        _upsert(db, Tenant, {"extern_ref": t["extern_ref"]}, {"name": t["name"]})[1]
        for t in TENANTS
    )


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
        for model in (Language, Tenant, Persona, PersonaObjection, Scenario, MetricType)
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
        for code in sorted({p["language_id"] for p in PERSONAS})
    )


# Seed text goes through the same sanitiser as authored text (ADR 0059): it is
# team-written and expected to be a no-op, so a change here is a seed bug caught
# at provisioning rather than a surprise in a live prompt.
def _seed_personas(db: DbSession) -> int:
    created = 0
    for p in PERSONAS:
        row, was_created = _upsert(
            db, Persona, {"key": p["id"]},
            {"name": clean(p["name"]), "role_label": clean(p["role_label"]),
             "role": clean(p["role"]), "traits": clean(p["traits"]),
             "behavior": clean(p["behavior"]),
             "training_goal": clean(p["training_goal"]), "difficulty": p["difficulty"],
             "active": True, "language_code": p["language_id"],
             "tts_voice": p["tts_voice"],
             "kugelaudio_voice_id": p["kugelaudio_voice_id"],
             # A shipped built-in belongs to nobody and everybody (ADR 0058).
             "created_by": None, "visibility": VISIBILITY_PUBLIC})
        created += was_created
        _seed_objections(db, row, p["objections"])
    return created


def _seed_objections(db: DbSession, persona: Persona, objections) -> None:
    """Bring one Persona's objections to the seed state (R-12, ADR 0045).

    Replaced wholesale rather than upserted: the list is what carries meaning,
    and `position` gives a single objection no natural key to match on. Not
    counted as created rows -- `inventory()` already reports the table.
    """
    db.flush()  # a freshly created Persona needs its id before rows point at it
    db.query(PersonaObjection).filter_by(
        persona_id=persona.persona_id).delete(synchronize_session=False)
    for index, text in enumerate(objections):
        db.add(PersonaObjection(
            persona_id=persona.persona_id, position=index, text=clean(text)))


def _seed_scenarios(db: DbSession) -> int:
    return sum(
        _upsert(db, Scenario, {"key": s["id"]},
                {"title": clean(s["name"]),
                 "short_description": clean(s["short_description"]),
                 "description": clean(s["description"]),
                 "case_facts": clean(s["case_facts"]),
                 "call_goal": clean(s["call_goal"]),
                 "success_condition": clean(s["success_condition"]),
                 "created_by": None, "visibility": VISIBILITY_PUBLIC})[1]
        for s in SCENARIOS
    )


def _seed_metric_types(db: DbSession) -> int:
    return sum(
        _upsert(db, MetricType, {"key": m.key},
                {"name": m.name, "unit": m.unit,
                 "feature_id": m.feature_id, "active": m.active})[1]
        for m in METRICS
    )
