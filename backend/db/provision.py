"""Migrate and seed, idempotently; run at startup and by seed_reference_data."""

from __future__ import annotations

import logging
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session as DbSession

from shared.db import ALEMBIC_INI
from shared.db.models import (
    AuthoredContent,
    FocusGoal,
    Language,
    MetricType,
    Persona,
    PersonaObjection,
    Scenario,
    Tenant,
    VISIBILITY_PUBLIC,
)
from shared.db.seed_data import FOCUS_GOALS, LANGUAGE_NAMES, PERSONAS, SCENARIOS, TENANTS
from shared.db.session import advisory_lock, session_scope
from shared.feedback.metrics import METRICS
from backend.authored_text import clean

logger = logging.getLogger(__name__)


def provision() -> dict[str, int]:
    logger.info("Migrating database to head...")
    config = Config(str(ALEMBIC_INI))
    # Keep our logging (see migrations/env.py).
    config.attributes["configure_logging"] = False
    command.upgrade(config, "head")
    # Locked like the migration, so concurrent seeds cannot race; taken only
    # now, since holding it across both would deadlock this process.
    logger.info("Seeding reference data...")
    with advisory_lock():
        with session_scope() as db:
            return seed(db)


def seed(db: DbSession) -> dict[str, int]:
    created = {
        "Language": _seed_languages(db),
        "Tenant": _seed_tenants(db),
        "Persona": _seed_personas(db),
        "Scenario": _seed_scenarios(db),
        "MetricType": _seed_metric_types(db),
        "FocusGoal": _seed_focus_goals(db),
    }
    # Deactivate, never delete: other rows reference these.
    _deactivate_missing(db, Persona, {p["id"] for p in PERSONAS})
    _deactivate_missing(db, Scenario, {s["id"] for s in SCENARIOS})
    _deactivate_missing(db, FocusGoal, {g["id"] for g in FOCUS_GOALS})
    _deactivate_missing(db, MetricType, {m.key for m in METRICS})
    return created


def _seed_tenants(db: DbSession) -> int:
    """Only `default`; companies are created on first login (ADR 0060)."""
    return sum(
        _upsert(db, Tenant, {"extern_ref": t["extern_ref"]}, {"name": t["name"]})[1]
        for t in TENANTS
    )


def _deactivate_missing(db: DbSession, model, seeded_keys: set[str]) -> None:
    """`created_by IS NULL` is load-bearing: authored rows sit beside seed rows,
    and without it a `key` default would deactivate every User's library at the
    next boot (test_seed pins this)."""
    query = db.query(model).filter(model.key.notin_(seeded_keys), model.active.is_(True))
    if issubclass(model, AuthoredContent):
        query = query.filter(model.created_by.is_(None))
    query.update({"active": False}, synchronize_session=False)


def inventory(db: DbSession) -> dict[str, int]:
    return {
        model.__name__: db.query(model).count()
        for model in (Language, Tenant, Persona, PersonaObjection, Scenario,
                      MetricType, FocusGoal)
    }


def _upsert(db: DbSession, model, natural_key: dict, values: dict):
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


# Seed text goes through the authored-text sanitiser too; any change is a seed bug.
def _seed_personas(db: DbSession) -> int:
    created = 0
    for p in PERSONAS:
        row, was_created = _upsert(
            db, Persona, {"key": p["id"]},
            {"name": clean(p["name"]), "role_label": clean(p["role_label"]),
             "role": clean(p["role"]), "traits": clean(p["traits"]),
             "traits_label": clean(p["traits_label"]),
             "behavior": clean(p["behavior"]),
             "training_goal": clean(p["training_goal"]),
             # A path, not prompt text.
             "avatar_url": p.get("avatar_url"),
             "active": p.get("active", True), "language_code": p["language_id"],
             "kugelaudio_voice_id": p["kugelaudio_voice_id"],
             "hard": p.get("hard", False)})
        created += was_created
        _seed_objections(db, row, p["objections"], p["objection_labels"])
    return created


def _seed_objections(db: DbSession, persona: Persona, objections, labels) -> None:
    """Replaced wholesale, so objection ids change every startup: never reference
    one by id."""
    db.flush()
    db.query(PersonaObjection).filter_by(
        persona_id=persona.persona_id).delete(synchronize_session=False)
    for index, (text, label) in enumerate(zip(objections, labels, strict=True)):
        db.add(PersonaObjection(
            persona_id=persona.persona_id, position=index,
            text=clean(text), text_label=clean(label)))


def _seed_scenarios(db: DbSession) -> int:
    return sum(
        _upsert(db, Scenario, {"key": s["id"]},
                {"title": clean(s["name"]),
                 "short_description": clean(s["short_description"]),
                 "briefing": clean(s["briefing"]),
                 "description": clean(s["description"]),
                 "case_facts": clean(s["case_facts"]),
                 "description_label": clean(s["description_label"]),
                 "case_facts_label": clean(s["case_facts_label"]),
                 "call_goal": clean(s["call_goal"]),
                 # A closed vocabulary, validated by its CHECK.
                 "category": s["category"],
                 # Written every run, or a returning built-in stays inactive.
                 "active": True,
                 "created_by": None, "visibility": VISIBILITY_PUBLIC})[1]
        for s in SCENARIOS
    )


def _seed_focus_goals(db: DbSession) -> int:
    """Not cleaned: none of this text reaches a prompt."""
    return sum(
        _upsert(db, FocusGoal, {"key": g["id"]},
                {"title": g["title"], "caption": g["caption"], "info": g["info"],
                 "group_key": g["group"], "evidence": g["evidence"],
                 "position": g["position"], "active": True})[1]
        for g in FOCUS_GOALS
    )


def _seed_metric_types(db: DbSession) -> int:
    return sum(
        _upsert(db, MetricType, {"key": m.key},
                {"name": m.name, "unit": m.unit, "aspect": m.aspect,
                 "feature_id": m.feature_id, "active": m.active})[1]
        for m in METRICS
    )
