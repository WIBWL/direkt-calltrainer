"""
Befuellt die Referenztabellen: Sprache, Persona, Szenario, MetrikTyp.

Idempotent: jeder Datensatz wird ueber seinen natuerlichen Schluessel
gesucht und bei Bedarf angelegt, sonst auf den Seed-Stand aktualisiert.
Mehrfaches Ausfuehren erzeugt daher keine Duplikate.

Quellen der Inhalte:
    Sprache/Persona/Szenario -> backend/languages.py, personas.py, scenarios.py
    MetrikTyp                -> docs/features.md (Abschnitt "Sprach- und
                                Kommunikationsanalyse"), Spalte Prio steuert
                                das aktiv-Flag: MUST -> True, sonst False.

Aufruf (Projekt-Wurzel, aktive .venv, laufende Postgres):
    python scripts/seed_reference_data.py
"""
import os
import sys

from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# .env laden, BEVOR backend.db.session importiert wird: dessen Modulcode
# liest DATABASE_URL beim Import aus der Umgebung.
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from backend.db.models import (  # noqa: E402
    MetrikTyp,
    Persona,
    PersonaEinwand,
    Sprache,
    Szenario,
)
from backend.db.session import session_scope  # noqa: E402
from backend.languages import LANGUAGES  # noqa: E402
from backend.personas import PERSONAS  # noqa: E402
from backend.scenarios import SCENARIOS  # noqa: E402


# --- Annahmen ------------------------------------------------------------
# Die ORM-Modelle verlangen Spalten, fuer die es in den hartcodierten
# Quellmodulen keinen Wert gibt. Defaults hier zentral und benannt:
#
# Persona.schwierigkeitsgrad: in personas.py nicht modelliert. Default
#   "mittel" — die einzige vorhandene Persona ist fordernd, aber nicht als
#   Eskalationsfall angelegt.
# Szenario.typ: in scenarios.py nicht modelliert. Abgeleitet aus F-03
#   ("Angebots- und Preisgespräche"), da das Szenario auf das Closing zielt.
DEFAULT_SCHWIERIGKEITSGRAD = "mittel"
DEFAULT_SZENARIO_TYP = "Angebots- und Preisgespräch"


# --- MetrikTyp: paraverbale Dimensionen aus docs/features.md -------------
# (schluessel, bezeichnung, einheit, feature_id, aktiv)
# einheit nur dort gesetzt, wo die Dimension eine eindeutige physikalische
# Messgroesse hat; qualitative Dimensionen bleiben bewusst ohne Einheit.
METRIK_TYPEN = [
    # MUST — MVP-Umfang
    ("intonation", "Analyse der Intonation", "Hz", "F-35", True),
    ("tempo", "Analyse des Sprechtempos", "Wörter/min", "F-36", True),
    ("lautstaerke", "Analyse der Lautstärke", "dB", "F-37", True),
    ("artikulation", "Analyse der Artikulation", None, "F-38", True),
    ("sprechfluessigkeit", "Analyse der Sprechflüssigkeit", None, "F-51", True),
    ("redundanz", "Erkennung überlanger oder überkomplexer Erklärungen", None, "F-08", True),
    # SHOULD / COULD — bewusst inaktiv, damit die MVP-Menge klar bleibt
    ("konkretheit", "Analyse der sprachlichen Konkretheit", None, "F-40", False),
    ("phasengerechte_sprache", "Phasengerechte Sprache", None, "F-42", False),
    ("redeanteile", "Analyse der Redeanteile", "%", "F-24", False),
    ("aktives_zuhoeren", "Erkennung aktiven Zuhörens", None, "F-41", False),
    ("kongruenz", "Kongruenz von Inhalt und Stimme", None, "F-39", False),
]


def upsert(db, model, natural_key: dict, werte: dict):
    """Legt den Datensatz an oder bringt ihn auf den Seed-Stand.

    Gibt (objekt, neu_angelegt) zurueck.
    """
    obj = db.query(model).filter_by(**natural_key).one_or_none()
    if obj is None:
        obj = model(**natural_key, **werte)
        db.add(obj)
        return obj, True
    for feld, wert in werte.items():
        setattr(obj, feld, wert)
    return obj, False


def seed_sprachen(db) -> int:
    neu = 0
    for code, bezeichnung in LANGUAGES.items():
        _, angelegt = upsert(
            db, Sprache, {"sprache_code": code}, {"bezeichnung": bezeichnung}
        )
        neu += angelegt
    return neu


def seed_einwaende(db, persona: Persona, einwaende: list[str]) -> None:
    """Bringt die Einwaende einer Persona auf den Seed-Stand.

    Abgleich ueber (persona_id, reihenfolge): vorhandene Positionen werden
    aktualisiert, ueberzaehlige entfernt. So bleiben die IDs ueber mehrere
    Laeufe stabil, statt bei jedem Lauf neu vergeben zu werden.
    """
    for position, text in enumerate(einwaende):
        vorhanden = (
            db.query(PersonaEinwand)
            .filter_by(persona_id=persona.persona_id, reihenfolge=position)
            .one_or_none()
        )
        if vorhanden is None:
            db.add(
                PersonaEinwand(
                    persona_id=persona.persona_id, reihenfolge=position, text=text
                )
            )
        else:
            vorhanden.text = text

    db.query(PersonaEinwand).filter(
        PersonaEinwand.persona_id == persona.persona_id,
        PersonaEinwand.reihenfolge >= len(einwaende),
    ).delete(synchronize_session=False)


def seed_personas(db) -> int:
    neu = 0
    for p in PERSONAS.values():
        persona, angelegt = upsert(
            db,
            Persona,
            {"schluessel": p.id},
            {
                "name": p.name,
                "rolle": p.role,
                "haltung": p.traits,
                "verhalten": p.behavior,
                "trainingsziel": p.training_goal,
                "schwierigkeitsgrad": DEFAULT_SCHWIERIGKEITSGRAD,
                "aktiv": True,
            },
        )
        neu += angelegt
        # persona_id wird erst beim Flush vergeben, die Einwaende brauchen sie.
        db.flush()
        seed_einwaende(db, persona, p.typical_objections)
    return neu


def seed_szenarien(db) -> int:
    neu = 0
    for s in SCENARIOS.values():
        _, angelegt = upsert(
            db,
            Szenario,
            {"schluessel": s.id},
            {
                "typ": DEFAULT_SZENARIO_TYP,
                "titel": s.name,
                "beschreibung": s.description,
            },
        )
        neu += angelegt
    return neu


def seed_metrik_typen(db) -> int:
    neu = 0
    for schluessel, bezeichnung, einheit, feature_id, aktiv in METRIK_TYPEN:
        _, angelegt = upsert(
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
        neu += angelegt
    return neu


def main() -> None:
    with session_scope() as db:
        neu_sprache = seed_sprachen(db)
        neu_persona = seed_personas(db)
        neu_szenario = seed_szenarien(db)
        neu_metrik = seed_metrik_typen(db)

        # Zaehlen in derselben Session, nach dem Flush der Inserts.
        db.flush()
        print("Neu angelegt: "
              f"Sprache {neu_sprache}, Persona {neu_persona}, "
              f"Szenario {neu_szenario}, MetrikTyp {neu_metrik}")
        print("Bestand:     "
              f"Sprache: {db.query(Sprache).count()}, "
              f"Persona: {db.query(Persona).count()}, "
              f"PersonaEinwand: {db.query(PersonaEinwand).count()}, "
              f"Szenario: {db.query(Szenario).count()}, "
              f"MetrikTyp: {db.query(MetrikTyp).count()}")


if __name__ == "__main__":
    main()
