"""The Persona and Scenario library: the mapping, and the seeded content.

Since ADR 0041 the library is database-backed, so there are two separate
things to check and this module keeps them apart:

  * `backend/library.py` maps a database row onto the frozen value object the
    rest of the backend passes around. Tested on rows built in memory — no
    database, per this suite's no-infrastructure rule.
  * `scripts/seed_reference_data.py` carries the library's initial content
    (ADR 0041), so the requirements about *what* the library covers are
    asserted against the seed data, which is importable without a database.

Covers:
  F-04  Kundenpersona-Bibliothek  (extensible; cost-critical customers,
        managing directors / IT leads focused on strategy & budget)
  F-03  Szenario-Typen  (support cases, pricing/offer talks, ...)
  F-01  the counterpart reflects conversational dynamics, not just facts
  R-07  cost-critical customer   R-08  budget-focused decision maker
  R-09  support + consulting     R-10  offer/price negotiation
  ADR 0041  Personas and Scenarios are loaded from the database
  ADR 0043  prompt fields are English, display fields are in the UI language;
            a Persona's language is its own, a Scenario carries none
  ADR 0045  the Scenario carries the case, the Persona carries the objections
  R-12  spontaneous objections
"""

import pytest

from backend.db import models
from backend.library import _to_persona, _to_scenario
from backend.personas import Persona, PersonaVoice
from backend.scenarios import Scenario
from backend.session.language_packs import LANGUAGE_PACKS
from tests.conftest import load_seed_module

# _to_persona/_to_scenario are the mapping this module is about.
# pylint: disable=missing-function-docstring,protected-access

SEED = load_seed_module()


# --- the mapping: database row -> value object --------------------------


def _persona_row(**overrides):
    fields = {
        "schluessel": "row-persona",
        "name": "Thomas Brandt",
        "rolle_anzeige": "Geschäftsführer, Fokus auf Strategie & Budget",
        "rolle": "Managing director of a mid-sized company",
        "haltung": "matter-of-fact, time-conscious",
        "verhalten": "You press for concrete answers.",
        "trainingsziel": "",
        "schwierigkeitsgrad": "mittel",
        "sprache_code": "de",
        "tts_stimme": "de_male",
        "kugelaudio_stimme_id": 1885,
        "aktiv": True,
        "sprache": models.Sprache(sprache_code="de", bezeichnung="Deutsch"),
    }
    return models.Persona(**{**fields, **overrides})


def test_persona_row_maps_onto_the_value_object():
    """ADR 0041: the German column names stop at `library.py`; callers get a
    plain dataclass."""
    persona = _to_persona(_persona_row())
    assert isinstance(persona, Persona)
    assert persona.id == "row-persona"
    assert persona.name == "Thomas Brandt"
    assert persona.role == "Managing director of a mid-sized company"
    assert persona.traits == "matter-of-fact, time-conscious"
    assert persona.behavior == "You press for concrete answers."


def test_persona_mapping_keeps_display_and_prompt_fields_apart():
    """ADR 0043: `rolle_anzeige` is the card's label, `rolle` is prompt input.
    One column each, and they must not be swapped."""
    persona = _to_persona(_persona_row())
    assert persona.role_label == "Geschäftsführer, Fokus auf Strategie & Budget"
    assert persona.role != persona.role_label


def test_persona_mapping_carries_language_and_both_voices():
    """ADR 0041/0043: the language is the Persona's own, and it names a voice
    for each TTS backend (ADR 0040: KugelAudio default, EFRE fallback)."""
    persona = _to_persona(_persona_row())
    assert persona.language_id == "de"
    assert persona.language_name == "Deutsch"
    assert isinstance(persona.voice, PersonaVoice)
    assert persona.voice.tts_voice == "de_male"
    assert persona.voice.kugelaudio_voice_id == 1885


def test_scenario_row_maps_onto_the_value_object():
    """ADR 0043: `kurzbeschreibung` is the teaser shown, `beschreibung` the
    English call context the model reads."""
    scenario = _to_scenario(
        models.Szenario(
            schluessel="row-scenario",
            typ="Angebots- und Preisgespräch",
            titel="Kündigungsabsicht wegen Preis",
            kurzbeschreibung="Der Kunde erwägt zu kündigen.",
            beschreibung="The customer is calling to say they are considering cancelling.",
        )
    )
    assert isinstance(scenario, Scenario)
    assert scenario.id == "row-scenario"
    assert scenario.name == "Kündigungsabsicht wegen Preis"
    assert scenario.short_description == "Der Kunde erwägt zu kündigen."
    assert scenario.description.startswith("The customer")


# --- the seeded content -------------------------------------------------


def test_seeded_persona_library_is_non_empty_and_well_formed():
    assert SEED.PERSONAS, "F-04: the library ships at least one persona"
    for entry in SEED.PERSONAS:
        assert entry["schluessel"] and entry["name"]
        assert entry["rolle"], "F-04: a persona carries a role"
        assert entry["rolle_anzeige"], "ADR 0043: and a label to show on the card"
        assert entry["haltung"], "F-01: a persona carries character traits"
        assert entry["verhalten"], "F-01: a persona carries a behaviour description"


def test_seeded_persona_keys_are_unique():
    keys = [p["schluessel"] for p in SEED.PERSONAS]
    assert len(keys) == len(set(keys))


def test_seeded_library_covers_the_budget_focused_decision_maker():
    """F-04 / R-08: a managing director or IT lead with a strategy & budget
    focus is representable. Asserted in English — ADR 0043 moved the prompt
    fields off German."""
    joined = " ".join(
        f"{p['rolle']} {p['haltung']} {p['verhalten']}".lower() for p in SEED.PERSONAS
    )
    assert "managing director" in joined or "it lead" in joined
    assert "budget" in joined or "strategy" in joined


def test_seeded_persona_behaviour_encodes_price_pushback():
    """F-04 / R-07: a cost-critical counterpart that presses on price."""
    joined = " ".join(p["verhalten"].lower() for p in SEED.PERSONAS)
    assert "price" in joined


def test_seeded_scenario_library_is_non_empty_and_well_formed():
    assert SEED.SZENARIEN, "F-03: the library ships at least one scenario"
    for entry in SEED.SZENARIEN:
        assert entry["schluessel"] and entry["titel"] and entry["typ"]
        assert entry["kurzbeschreibung"], "ADR 0043: the card shows a teaser"
        assert len(entry["beschreibung"]) > 40, "the model gets a real call context"


def test_seeded_scenario_keys_are_unique():
    keys = [s["schluessel"] for s in SEED.SZENARIEN]
    assert len(keys) == len(set(keys))


def test_seeded_scenarios_cover_support_and_pricing_contexts():
    """F-03 / R-09 / R-10: at least a support-style case and a
    price/cancellation negotiation are trainable."""
    blob = " ".join(f"{s['titel']} {s['beschreibung']}".lower() for s in SEED.SZENARIEN)
    assert "support" in blob
    assert "cancel" in blob or "price" in blob


@pytest.mark.parametrize("entry", SEED.PERSONAS, ids=lambda e: e["schluessel"])
def test_every_seeded_persona_speaks_a_language_that_has_a_pack(entry):
    """ADR 0043: a Persona's `sprache_code` decides the spoken language, and
    `get_pack` raises for one without a pack — a configuration error that
    would only surface once a Session starts."""
    assert entry["sprache_code"] in LANGUAGE_PACKS


@pytest.mark.parametrize("entry", SEED.PERSONAS, ids=lambda e: e["schluessel"])
def test_every_seeded_persona_has_its_own_voice(entry):
    """ADR 0040/0041: voice is a per-Persona property, and both backends need
    an identity — KugelAudio by default, the EFRE model as fallback."""
    assert entry["tts_stimme"]
    assert isinstance(entry["kugelaudio_stimme_id"], int)


def test_seeded_scenarios_carry_no_language_of_their_own():
    """ADR 0043: Scenarios stay language-neutral, which is what keeps every
    Persona x Scenario pairing valid (ADR 0001, ADR 0015)."""
    for entry in SEED.SZENARIEN:
        assert "sprache_code" not in entry
        assert "sprache" not in entry


# --- ADR 0045: the case on the Scenario, the objections on the Persona ---


def test_scenario_row_maps_the_case_fields():
    """ADR 0045: three columns, three fields — the case is addressable, not
    buried in the prose of `beschreibung`."""
    scenario = _to_scenario(
        models.Szenario(
            schluessel="row-case",
            typ="Angebots- und Preisgespräch",
            titel="Kündigungsabsicht wegen Preis",
            kurzbeschreibung="Der Kunde erwägt zu kündigen.",
            beschreibung="The customer is calling to say they are considering cancelling.",
            fallfakten="14 licences, 1,180 euros a month since March last year.",
            anrufziel="Get the price down, or a clear reason why not.",
            erfolgsbedingung="Settled once a specific figure with a date is committed to.",
        )
    )
    assert scenario.case_facts == "14 licences, 1,180 euros a month since March last year."
    assert scenario.call_goal == "Get the price down, or a clear reason why not."
    assert scenario.success_condition == (
        "Settled once a specific figure with a date is committed to."
    )


def test_persona_row_maps_its_objections_in_order():
    """R-12 / ADR 0026: the objections are ordered rows, and `reihenfolge` is
    what orders them — `library.py` has to load and keep that order."""
    row = _persona_row(
        einwaende=[
            models.PersonaEinwand(reihenfolge=1, text="second objection"),
            models.PersonaEinwand(reihenfolge=0, text="first objection"),
        ]
    )
    persona = _to_persona(row)
    assert persona.objections == ("first objection", "second objection")


def test_persona_without_objections_maps_to_an_empty_tuple():
    """A Persona need not have objections; the prompt then omits the block."""
    assert _to_persona(_persona_row(einwaende=[])).objections == ()


def test_objections_carry_no_language_of_their_own():
    """ADR 0043/0045: a Persona has a fixed language, and `persona_einwand` has
    no language column — which is why objections are authored in English, as
    moves rather than as quotable lines."""
    assert not hasattr(models.PersonaEinwand, "sprache_code")
    assert not hasattr(models.PersonaEinwand, "sprache")


def test_seeded_scenarios_carry_the_case():
    """ADR 0045: every shipped Scenario states its facts, the caller's goal and
    the condition under which the matter is settled."""
    for entry in SEED.SZENARIEN:
        assert entry["fallfakten"].strip(), f"{entry['schluessel']}: no case facts"
        assert entry["anrufziel"].strip(), f"{entry['schluessel']}: no call goal"
        assert entry["erfolgsbedingung"].strip(), f"{entry['schluessel']}: no success condition"


def test_seeded_scenario_context_does_not_carry_the_trainer_objective():
    """ADR 0045, the defect that prompted it: `beschreibung` used to end with
    what the *user* is meant to achieve ("keep the customer through price
    negotiation"), addressed to the Persona — who is the customer. The caller's
    own goal lives in `anrufziel` now, and nothing hands it the trainee's."""
    for entry in SEED.SZENARIEN:
        lowered = entry["beschreibung"].lower()
        assert "the goal of the call is" not in lowered, entry["schluessel"]
        assert "goal of the call" not in lowered, entry["schluessel"]


def test_seeded_personas_carry_objections():
    """R-12: `persona_einwand` has been empty since ADR 0026 created it. Three
    to four per Persona is what ADR 0045 asks for."""
    for entry in SEED.PERSONAS:
        objections = entry["einwaende"]
        assert 3 <= len(objections) <= 4, f"{entry['schluessel']}: {len(objections)} objections"
        assert all(text.strip() for text in objections)


def test_seeded_persona_behaviour_carries_no_situation():
    """ADR 0045: `verhalten` is manner only. Both Personas used to open it with
    the same sentence about having a reason for the call — a statement about
    the Session's setup that the prompt frame already makes."""
    for entry in SEED.PERSONAS:
        lowered = entry["verhalten"].lower()
        assert "reason for this call" not in lowered, entry["schluessel"]
        assert "context of the call" not in lowered, entry["schluessel"]
