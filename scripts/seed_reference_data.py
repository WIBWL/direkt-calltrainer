"""
Fills the reference tables: Sprache, Persona, Szenario, MetrikTyp.

Idempotent: every record is looked up by its natural key and either created
or brought back to the seed state, so repeated runs produce no duplicates.

Content sources:
    Persona/Szenario -> this file (ADR 0041: the database is the source of
                        truth, and this script holds its initial content;
                        the backend no longer hardcodes either)
    Sprache          -> the sprache_code values the Personas use
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


# --- Personas -----------------------------------------------------------
# Every Persona has exactly one Language and one voice (ADR 0041). Two voice
# values per Persona: kugelaudio_stimme_id for the default TTS backend,
# tts_stimme for the EFRE fallback (ADR 0040).
#
# Known gap: the EFRE fallback model only carries German voices — de_male and
# de_female work, every English voice name it was probed with returns a 500.
# An English Persona therefore has no usable fallback voice and effectively
# depends on KugelAudio being up; its tts_stimme is set to a German voice only
# so the NOT NULL column has a value.
#
# Two kinds of text per entry (ADR 0043): "rolle_anzeige" is the label shown on
# the selection card and is written in the UI language; "rolle"/"haltung"/
# "verhalten" are read only by the model and are English, so that the language
# the Persona speaks is decided by sprache_code alone.
SPRACH_BEZEICHNUNGEN = {"de": "Deutsch", "en": "Englisch"}

PERSONAS = [
    {
        "schluessel": "thomas-brandt-ceo",
        "name": "Thomas Brandt",
        "rolle_anzeige": "Geschäftsführer, Fokus auf Strategie & Budget",
        "rolle": "Managing director of a mid-sized company, focused on strategy and budget",
        "haltung": (
            "matter-of-fact, time-conscious, impatient with overly technical "
            "detail, an experienced negotiator"
        ),
        # Manner only (ADR 0045): how hard this Persona pushes and how long it
        # tolerates a vague answer. What the call is about lives on the
        # Scenario.
        "verhalten": (
            "You lose patience quickly with technical, evasive or convoluted "
            "answers and say so — two of them in a row and you cut in to ask "
            "for the short version. You expect a number, a date or a name, and "
            "you repeat the question until you get one. On price you are the "
            "most persistent: a justification that stays general gets pushed "
            "back on every time it comes up. A concrete answer settles the "
            "matter for you immediately and you say so; you do not keep "
            "grinding once you have one"
        ),
        # Not modelled before this script took over the content: "mittel"
        # because this Persona is demanding but not an escalation case, and
        # no training goal has been written for it yet.
        "trainingsziel": "",
        "schwierigkeitsgrad": "mittel",
        "sprache_code": "de",
        "tts_stimme": "de_male",
        "kugelaudio_stimme_id": 1885,
        # R-12 / ADR 0045: moves, not quotable lines -- the model reuses quoted
        # examples verbatim, and these have to work in any Scenario.
        "einwaende": [
            "pushes back that the figure is above what was budgeted for this",
            "says this was promised once before and nothing came of it",
            "asks what exactly is being paid for, item by item",
            "threatens to take the decision to the next budget round instead",
        ],
    },
    {
        "schluessel": "samantha-ferris-marketing",
        "name": "Samantha Ferris",
        "rolle_anzeige": "Marketing-Managerin bei einem Kundenunternehmen",
        "rolle": "Marketing manager at a company that is a customer of the user's",
        "haltung": (
            "very polite, courteous, calm and composed, never pushy, easy and "
            "pleasant to talk to"
        ),
        # Manner only (ADR 0045). Same persistence as the other Persona, worn
        # differently: she never raises her voice and never interrupts, and
        # that is the whole difference.
        "verhalten": (
            "You never interrupt and never raise your voice, and you give the "
            "other person time to finish even when the answer is going "
            "nowhere. You are just as hard to satisfy as anyone impatient, "
            "only politely: a vague answer gets a friendly restatement of the "
            "same question, and you will ask a third and fourth time without "
            "any edge in your voice. You apologise for pressing while you do "
            "it. Once an answer is concrete you accept it warmly and stop"
        ),
        "trainingsziel": "",
        "schwierigkeitsgrad": "leicht",
        "sprache_code": "en",
        # tts_stimme is a German voice because the EFRE fallback has no
        # English one — see the note above.
        "tts_stimme": "de_female",
        "kugelaudio_stimme_id": 1071,
        "einwaende": [
            "apologises, then returns to the question that was not answered",
            "says she understands, but that this does not answer what she asked",
            "asks whether she should call back once someone can give her a firm answer",
        ],
    },
]

# --- Szenarien ----------------------------------------------------------
# `typ` follows F-03's categories of Szenario-Typen.
#
# Szenarien carry no language of their own (ADR 0043). "titel" and
# "kurzbeschreibung" are the display texts in the UI language; the rest is the
# English call context the model reads — which is what lets any Persona run any
# Szenario regardless of the language that Persona speaks.
#
# Four prompt fields (ADR 0045): "beschreibung" is the situation, and
# "fallfakten"/"anrufziel"/"erfolgsbedingung" are the case. Two authoring rules
# hold them together:
#   * The facts are about the *case*, never about the caller — no name, no
#     employer, no motive — because both Personas have to be able to carry
#     them (ADR 0001, ADR 0015).
#   * "anrufziel" is what the *caller* wants. What the user is meant to achieve
#     is not part of the Persona's prompt; it used to be, and the caller was
#     being told to keep itself as a customer.
SZENARIEN = [
    {
        "schluessel": "cold-call-followup",
        "typ": "Angebots- und Preisgespräch",
        "titel": "Offenes Anliegen zu bestehendem Vertrag",
        "kurzbeschreibung": (
            "Der Kunde ruft mit einer offenen Frage zu einem bestehenden "
            "Vertrag an und will sie geklärt haben."
        ),
        "beschreibung": (
            "The customer (the persona) is calling the user, who works in "
            "support, about an unresolved issue with an existing contract."
        ),
        "fallfakten": (
            "A support ticket was opened eleven days ago about exports failing "
            "for one of the two team accounts. It was acknowledged the same "
            "day, a callback was promised within 48 hours, and nothing has "
            "happened since. The workaround in use is exporting one record at "
            "a time, roughly 40 a week. The contract runs to the end of the "
            "year and includes next-business-day support."
        ),
        "anrufziel": (
            "Find out what is actually happening with the ticket and get a "
            "date by which the export works again."
        ),
        "erfolgsbedingung": (
            "someone names what is wrong and when it will be fixed, or says "
            "plainly that it cannot be fixed and what happens instead. A "
            "promise to look into it is not enough on its own — that already "
            "happened eleven days ago."
        ),
    },
    {
        "schluessel": "price-cancellation-risk",
        "typ": "Angebots- und Preisgespräch",
        "titel": "Kündigungsabsicht wegen Preis",
        "kurzbeschreibung": (
            "Der Kunde erwägt zu kündigen, weil ihm die laufenden Kosten zu "
            "hoch sind."
        ),
        "beschreibung": (
            "The customer (the persona) is calling to say they are considering "
            "cancelling or downgrading, because the running costs seem too "
            "high relative to the benefit. The customer is still open to a "
            "conversation in principle."
        ),
        "fallfakten": (
            "The \"Insight Analytics\" package: 14 licences at 1,180 euros a "
            "month, running since March last year. The most recent renewal "
            "raised it by 12 percent, from 1,050 euros, with no change to what "
            "is included. Two of the package's six modules are in regular use; "
            "a competitor quoted roughly 800 euros for what looks like the "
            "same scope."
        ),
        "anrufziel": (
            "Get the price down, or get a clear reason why it cannot come "
            "down. Cancelling is a real option and one you say out loud."
        ),
        "erfolgsbedingung": (
            "a specific figure is committed to together with a date it takes "
            "effect from, or it is stated plainly that there will be no "
            "reduction and why. An offer to check internally and come back is "
            "not a result."
        ),
    },
]


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
    for code in sorted({p["sprache_code"] for p in PERSONAS}):
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
    No Persona carries objections today, so the list is empty and this only
    prunes rows left over from earlier seed runs.
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
    for entry in PERSONAS:
        values = {k: v for k, v in entry.items() if k not in ("schluessel", "einwaende")}
        persona, is_new = upsert(
            db, Persona, {"schluessel": entry["schluessel"]}, {**values, "aktiv": True}
        )
        created += is_new
        # persona_id is only assigned on flush, and the objections need it.
        db.flush()
        seed_einwaende(db, persona, entry["einwaende"])
    return created


def seed_szenarien(db) -> int:
    created = 0
    for entry in SZENARIEN:
        values = {k: v for k, v in entry.items() if k != "schluessel"}
        _, is_new = upsert(db, Szenario, {"schluessel": entry["schluessel"]}, values)
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
