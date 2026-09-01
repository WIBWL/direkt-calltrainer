"""
Fills the reference tables: Language, Persona, Scenario, MetricType.

Idempotent: every record is looked up by its natural key and either created
or brought back to the seed state, so repeated runs produce no duplicates.

Content sources:
    Persona/Scenario -> backend/personas.py, backend/scenarios.py
    Language         -> the language_ids the Personas use
    MetricType       -> docs/features.md, section "Sprach- und Kommunikationsanalyse"; 
                        its Prio column drives the aktiv flag (MUST -> True, otherwise False).

Run from the project root, with an active .venv and a running Postgres:
    python scripts/seed_reference_data.py
"""
import os
import sys

from dotenv import load_dotenv

# A script, not a package: the project root has to be on the search path
# before the backend imports, hence the noqa markers on them.
# pylint: disable=wrong-import-position
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from backend.db.models import Language, MetricType, Persona, PersonaObjection, Scenario  # noqa: E402
from backend.db.session import session_scope  # noqa: E402
from backend.personas import PERSONAS  # noqa: E402
from backend.scenarios import SCENARIOS  # noqa: E402


# --- Assumptions ---------------------------------------------------------
# Columns the ORM requires but the hardcoded source modules do not provide:
#
# Persona.difficulty: not modelled in personas.py. "mittel" because
#   the one existing Persona is demanding, but not an escalation case.
# Persona.training_goal: not modelled in personas.py. Left empty rather than
#   invented here — the Personas carry no training goal today.
# Scenario.scenario_type: not modelled in scenarios.py. Derived from F-03 ("Angebots-
#   und Preisgespräche"), as the scenario aims at the closing.
# Language.name: personas.py only carries the language code, so the
#   display names live here, for the codes the Personas actually use.
DEFAULT_DIFFICULTY = "mittel"
DEFAULT_TRAINING_GOAL = ""
DEFAULT_SCENARIO_TYPE = "Angebots- und Preisgespräch"
LANGUAGE_NAMES = {"de": "Deutsch", "en": "English"}

# --- MetricType: paraverbal dimensions from docs/features.md --------------
# (key, name, unit, feature_id, active)
# unit is set only where the dimension has an unambiguous physical unit;
# qualitative dimensions stay without one.
METRIC_TYPES = [
    # MUST — part of the MVP
    ("intonation", "Analyse der Intonation", "Hz", "F-35", True),
    ("speaking_rate", "Analyse des Sprechtempos", "Wörter/min", "F-36", True),
    ("loudness", "Analyse der Lautstärke", "dB", "F-37", True),
    ("articulation", "Analyse der Artikulation", None, "F-38", True),
    ("fluency", "Analyse der Sprechflüssigkeit", None, "F-51", True),
    ("redundancy", "Erkennung überlanger oder überkomplexer Erklärungen", None, "F-08", True),
    # SHOULD / COULD — inactive, so the MVP scope stays unambiguous
    ("concreteness", "Analyse der sprachlichen Konkretheit", None, "F-40", False),
    ("phase_appropriate_language", "Phasengerechte Sprache", None, "F-42", False),
    ("talk_time_share", "Analyse der Redeanteile", "%", "F-24", False),
    ("active_listening", "Erkennung aktiven Zuhörens", None, "F-41", False),
    ("congruence", "Kongruenz von Inhalt und Stimme", None, "F-39", False),
]

# Languages are never deactivated: they are a closed code list, and a Session
# keeps pointing at the code it ran in even once no Persona uses it any more.
DEACTIVATABLE = [
    ("Persona", Persona, lambda: {p.id for p in PERSONAS}),
    ("Scenario", Scenario, lambda: {s.id for s in SCENARIOS}),
    ("MetricType", MetricType, lambda: {m[0] for m in METRIC_TYPES}),
]


# Order of the inventory line printed at the end.
INVENTORY_TABLES = [
    ("Language", Language),
    ("Persona", Persona),
    ("PersonaObjection", PersonaObjection),
    ("Scenario", Scenario),
    ("MetricType", MetricType),
]


def upsert(db, model, natural_key: dict, values: dict):
    """Creates the record or brings it back to the seed state.

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


def seed_languages(db) -> int:
    """Upserts the Languages the Personas actually reference. Returns how many were created."""
    created = 0
    for code in sorted({p.language_id for p in PERSONAS}):
        _, is_new = upsert(
            db,
            Language,
            {"code": code},
            {"name": LANGUAGE_NAMES.get(code, code)},
        )
        created += is_new
    return created


def seed_objections(db, persona: Persona, objections: list[str]) -> None:
    """Brings a Persona's objections back to the seed state.

    Matched on (persona_id, position) so that existing positions are
    updated and surplus ones deleted, which keeps the IDs stable across runs.
    personas.py no longer models objections, so the list is empty today and
    this only prunes rows left over from earlier seed runs.
    """
    for position, text in enumerate(objections):
        existing = (
            db.query(PersonaObjection)
            .filter_by(persona_id=persona.persona_id, position=position)
            .one_or_none()
        )
        if existing is None:
            db.add(
                PersonaObjection(
                    persona_id=persona.persona_id, position=position, text=text
                )
            )
        else:
            existing.text = text

    db.query(PersonaObjection).filter(
        PersonaObjection.persona_id == persona.persona_id,
        PersonaObjection.position >= len(objections),
    ).delete(synchronize_session=False)


def seed_personas(db) -> int:
    """Upserts every Persona from personas.py, including its Language and voice."""
    created = 0
    for p in PERSONAS:
        persona, is_new = upsert(
            db,
            Persona,
            {"key": p.id},
            {
                "name": p.name,
                "role": p.role,
                "traits": p.traits,
                "behavior": p.behavior,
                "training_goal": DEFAULT_TRAINING_GOAL,
                "difficulty": DEFAULT_DIFFICULTY,
                "language_code": p.language_id,
                "tts_voice": p.voice.tts_voice,
                "kugelaudio_voice_id": p.voice.kugelaudio_voice_id,
                "active": True,
            },
        )
        created += is_new
        # persona_id is only assigned on flush, and the objections need it.
        db.flush()
        seed_objections(db, persona, [])
    return created


def seed_scenarios(db) -> int:
    """Upserts every Scenario from scenarios.py."""
    created = 0
    for s in SCENARIOS:
        _, is_new = upsert(
            db,
            Scenario,
            {"key": s.id},
            {
                "scenario_type": DEFAULT_SCENARIO_TYPE,
                "title": s.name,
                "description": s.description,
                "active": True,
            },
        )
        created += is_new
    return created


def deactivate_missing(db) -> dict[str, int]:
    """Deactivates Personas/Scenarios that the seed no longer contains.

    Deliberately not a delete: `session` references both by foreign key, and a
    past Session has to stay readable even once the Persona it used is retired.

    Note for ADR 0024 (User-authored Personas/Szenarien): once Users can create
    their own, this would wrongly deactivate them too, because nothing yet
    distinguishes a seeded row from a user-created one. That needs a provenance
    column before user authoring lands.
    """
    deactivated = {}
    for label, model, seed_keys in DEACTIVATABLE:
        count = (
            db.query(model)
            .filter(model.key.notin_(seed_keys()), model.active.is_(True))
            .update({"active": False}, synchronize_session=False)
        )
        deactivated[label] = count
    return deactivated


def seed_metric_types(db) -> int:
    """Upserts the paraverbal metric types from docs/features.md."""
    created = 0
    for key, name, unit, feature_id, active in METRIC_TYPES:
        _, is_new = upsert(
            db,
            MetricType,
            {"key": key},
            {
                "name": name,
                "unit": unit,
                "feature_id": feature_id,
                "active": active,
            },
        )
        created += is_new
    return created


def main() -> None:
    """Seeds every reference table, then reports what changed."""
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
    with session_scope() as db:
        created = {
            "Language": seed_languages(db),
            "Persona": seed_personas(db),
            "Scenario": seed_scenarios(db),
            "MetricType": seed_metric_types(db),
        }
        # After the upserts, so a record that is both present and active stays so.
        deactivated = deactivate_missing(db)
        # Count in the same session, after the inserts have been flushed.
        db.flush()
        inventory = {name: db.query(model).count() for name, model in INVENTORY_TABLES}

    print("Created:     ", ", ".join(f"{k} {v}" for k, v in created.items()))
    print("Deactivated: ", ", ".join(f"{k} {v}" for k, v in deactivated.items()))
    print("Inventory:   ", ", ".join(f"{k} {v}" for k, v in inventory.items()))


if __name__ == "__main__":
    main()
