"""Bringing an empty database up to a usable state: migrate, then seed.

Run at startup and by scripts/seed_reference_data.py; both halves idempotent.
Content comes from backend/db/seed_data.py (ADR 0041/0076) and, for MetricType,
backend/feedback/metrics.py, so inventory and analysis cannot drift apart."""

from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session as DbSession

from backend.authored_text import clean
from backend.db.models import (
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
from backend.db.seed_data import (
    FOCUS_GOALS,
    LANGUAGE_NAMES,
    PERSONAS,
    SCENARIOS,
    TENANTS,
)
from backend.db.session import advisory_lock, session_scope
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
    # Locked like the migration: two `_upsert`s racing would fail on the natural
    # key and log "Database provisioning failed". Same key, taken only now --
    # env.py has released it; holding both would make this process wait on
    # itself, since each takes it on its own connection.
    logger.info("Seeding reference data...")
    with advisory_lock():
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
        "FocusGoal": _seed_focus_goals(db),
    }
    # Deactivate, never delete: `session` references these rows, and the
    # routes filter on `active`.
    _deactivate_missing(db, Persona, {p["id"] for p in PERSONAS})
    _deactivate_missing(db, Scenario, {s["id"] for s in SCENARIOS})
    # The same rule for the focus catalogue (ADR 0076): `focus_selection_goal`
    # references it, so a retired goal stays readable for the selections that
    # already name it, and /api/focus filters on `active`.
    _deactivate_missing(db, FocusGoal, {g["id"] for g in FOCUS_GOALS})
    # The metric inventory too (ADR 0057): retired keys must not stay active
    # beside their replacements; measurements reference them, so no delete.
    _deactivate_missing(db, MetricType, {m.key for m in METRICS})
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
    """Sets `active` to False on every row *the seed created* and no longer contains.

    The `created_by IS NULL` scope is load-bearing: `AuthoredContent` tables
    (ADR 0058) hold User rows beside the shipped ones, and this runs at every
    start. Without it they survive only because an authored row has no `key`
    and `NULL NOT IN (...)` is not TRUE -- giving `key` a default or backfilling
    it would silently deactivate every User's library on the next boot.
    """
    query = db.query(model).filter(model.key.notin_(seeded_keys), model.active.is_(True))
    if issubclass(model, AuthoredContent):
        query = query.filter(model.created_by.is_(None))
    query.update({"active": False}, synchronize_session=False)


def inventory(db: DbSession) -> dict[str, int]:
    """Row counts of the reference tables, for the CLI's summary line."""
    return {
        model.__name__: db.query(model).count()
        for model in (Language, Tenant, Persona, PersonaObjection, Scenario,
                      MetricType, FocusGoal)
    }


def _upsert(db: DbSession, model, natural_key: dict, values: dict):
    """Create the record or bring it back to the seed state; returns (object, created)."""
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
             "traits_label": clean(p["traits_label"]),
             "behavior": clean(p["behavior"]),
             "training_goal": clean(p["training_goal"]), "difficulty": p["difficulty"],
             # Not cleaned: a path, not prompt text (ADR 0059). `active` is
             # False only while something the Persona needs (a voice id) is missing.
             "avatar_url": p.get("avatar_url"),
             "active": p.get("active", True), "language_code": p["language_id"],
             "kugelaudio_voice_id": p["kugelaudio_voice_id"],
             # A shipped built-in belongs to nobody and everybody (ADR 0058).
             "created_by": None, "visibility": VISIBILITY_PUBLIC})
        created += was_created
        _seed_objections(db, row, p["objections"], p["objection_labels"])
    return created


def _seed_objections(db: DbSession, persona: Persona, objections, labels) -> None:
    """Bring one Persona's objections to the seed state (R-12, ADR 0045).

    Replaced wholesale (no natural key), so their ids change on every startup:
    never reference an objection by id -- use persona and position, or add a
    stable key first. English `objections` and German `labels` are written in one
    pass so they cannot drift; tests/test_persona_scenario_library.py pins them.
    """
    db.flush()  # a freshly created Persona needs its id before rows point at it
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
                 # Not cleaned: a closed vocabulary, not authored prose, and
                 # the CHECK constraint is what validates it (ADR 0072).
                 "category": s["category"],
                 # Written every run, or a built-in that once dropped out of the
                 # seed stays inactive after it returns. Only seed rows (with a
                 # `key`) are reached, so no User-deleted Scenario is revived.
                 "active": True,
                 "created_by": None, "visibility": VISIBILITY_PUBLIC})[1]
        for s in SCENARIOS
    )


def _seed_focus_goals(db: DbSession) -> int:
    """The focus-goal catalogue (F-62, ADR 0076).

    Not cleaned: unlike a Persona or a Scenario, none of this text ever reaches
    a prompt, so the sanitiser of ADR 0059 has nothing to protect here.
    """
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
