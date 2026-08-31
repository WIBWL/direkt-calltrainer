"""
Fills the reference tables: Sprache, Persona, Szenario, MetrikTyp.

Idempotent: every record is looked up by its natural key and either created
or brought back to the seed state, so repeated runs produce no duplicates.

Content sources:
    Persona/Szenario -> backend/personas.py, backend/scenarios.py
    Sprache          -> the language_ids the Personas use
    MetrikTyp        -> docs/features.md, section "Sprach- und Kommunikationsanalyse"; 
                        its Prio column drives the aktiv flag (MUST -> True, otherwise False).

Run from the project root, with an active .venv and a running Postgres:
    python scripts/seed_reference_data.py
"""
import os
import sys

from dotenv import load_dotenv

# A script, not a package: the project root has to be on the search path
# before the backend imports, hence the noqa markers on them.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from backend.db.models import MetrikTyp, Persona, PersonaEinwand, Sprache, Szenario # noqa: E402
from backend.db.session import session_scope  # noqa: E402
from backend.personas import PERSONAS  # noqa: E402
from backend.scenarios import SCENARIOS  # noqa: E402


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


# --- MetrikTyp: paraverbal dimensions from docs/features.md --------------
# (schluessel, bezeichnung, einheit, feature_id, aktiv)
# einheit is set only where the dimension has an unambiguous physical unit;
# qualitative dimensions stay without one.
METRIK_TYPEN = [
    # MUST — part of the MVP
    ("intonation", "Analyse der Intonation", "Hz", "F-35", True),
    ("tempo", "Analyse des Sprechtempos", "Wörter/min", "F-36", True),
    ("lautstaerke", "Analyse der Lautstärke", "dB", "F-37", True),
    ("artikulation", "Analyse der Artikulation", None, "F-38", True),
    ("sprechfluessigkeit", "Analyse der Sprechflüssigkeit", None, "F-51", True),
    ("redundanz", "Erkennung überlanger oder überkomplexer Erklärungen", None, "F-08", True),
    # SHOULD / COULD — inactive, so the MVP scope stays unambiguous
    ("konkretheit", "Analyse der sprachlichen Konkretheit", None, "F-40", False),
    ("phasengerechte_sprache", "Phasengerechte Sprache", None, "F-42", False),
    ("redeanteile", "Analyse der Redeanteile", "%", "F-24", False),
    ("aktives_zuhoeren", "Erkennung aktiven Zuhörens", None, "F-41", False),
    ("kongruenz", "Kongruenz von Inhalt und Stimme", None, "F-39", False),
]

# Order of the inventory line printed at the end.
INVENTORY_TABLES = [
    ("Sprache", Sprache),
    ("Persona", Persona),
    ("PersonaEinwand", PersonaEinwand),
    ("Szenario", Szenario),
    ("MetrikTyp", MetrikTyp),
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


def seed_sprachen(db) -> int:
    created = 0
    for code in sorted({p.language_id for p in PERSONAS}):
        _, is_new = upsert(
            db,
            Sprache,
            {"sprache_code": code},
            {"bezeichnung": SPRACH_BEZEICHNUNGEN.get(code, code)},
        )
        created += is_new
    return created


def seed_einwaende(db, persona: Persona, objections: list[str]) -> None:
    """Brings a Persona's objections back to the seed state.

    Matched on (persona_id, reihenfolge) so that existing positions are
    updated and surplus ones deleted, which keeps the IDs stable across runs.
    personas.py no longer models objections, so the list is empty today and
    this only prunes rows left over from earlier seed runs.
    """
    for position, text in enumerate(objections):
        existing = (
            db.query(PersonaEinwand)
            .filter_by(persona_id=persona.persona_id, reihenfolge=position)
            .one_or_none()
        )
        if existing is None:
            db.add(
                PersonaEinwand(
                    persona_id=persona.persona_id, reihenfolge=position, text=text
                )
            )
        else:
            existing.text = text

    db.query(PersonaEinwand).filter(
        PersonaEinwand.persona_id == persona.persona_id,
        PersonaEinwand.reihenfolge >= len(objections),
    ).delete(synchronize_session=False)


def seed_personas(db) -> int:
    created = 0
    for p in PERSONAS:
        persona, is_new = upsert(
            db,
            Persona,
            {"schluessel": p.id},
            {
                "name": p.name,
                "rolle": p.role,
                "haltung": p.traits,
                "verhalten": p.behavior,
                "trainingsziel": DEFAULT_TRAININGSZIEL,
                "schwierigkeitsgrad": DEFAULT_SCHWIERIGKEITSGRAD,
                "aktiv": True,
            },
        )
        created += is_new
        # persona_id is only assigned on flush, and the objections need it.
        db.flush()
        seed_einwaende(db, persona, [])
    return created


def seed_szenarien(db) -> int:
    created = 0
    for s in SCENARIOS:
        _, is_new = upsert(
            db,
            Szenario,
            {"schluessel": s.id},
            {
                "typ": DEFAULT_SZENARIO_TYP,
                "titel": s.name,
                "beschreibung": s.description,
            },
        )
        created += is_new
    return created


def seed_metrik_typen(db) -> int:
    created = 0
    for schluessel, bezeichnung, einheit, feature_id, aktiv in METRIK_TYPEN:
        _, is_new = upsert(
            db,
            MetrikTyp,
            {"schluessel": schluessel},
            {
                "bezeichnung": bezeichnung,
                "einheit": einheit,
                "feature_id": feature_id,
                "aktiv": aktiv,
            },
        )
        created += is_new
    return created


def main() -> None:
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
    with session_scope() as db:
        created = {
            "Sprache": seed_sprachen(db),
            "Persona": seed_personas(db),
            "Szenario": seed_szenarien(db),
            "MetrikTyp": seed_metrik_typen(db),
        }
        # Count in the same session, after the inserts have been flushed.
        db.flush()
        inventory = {name: db.query(model).count() for name, model in INVENTORY_TABLES}

    print("Created:  ", ", ".join(f"{k} {v}" for k, v in created.items()))
    print("Inventory:", ", ".join(f"{k} {v}" for k, v in inventory.items()))


if __name__ == "__main__":
    main()
