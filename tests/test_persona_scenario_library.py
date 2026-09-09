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
  F-04  customer persona library  (extensible; cost-critical customers,
        managing directors / IT leads focused on strategy & budget)
  F-03  scenario types  (support cases, pricing/offer talks, ...)
  F-01  the counterpart reflects conversational dynamics, not just facts
  R-07  cost-critical customer   R-08  budget-focused decision maker
  R-09  support + consulting     R-10  offer/price negotiation
  ADR 0041  Personas and Scenarios are loaded from the database
  ADR 0043  prompt fields are English, display fields are in the UI language;
            a Persona's language is its own, a Scenario carries none
  ADR 0045  the Scenario carries the case, the Persona carries the objections
  R-12  spontaneous objections
"""

import re
import uuid

import pytest

from backend.db import models
from backend.library import _to_persona, _to_scenario
from backend.personas import Persona, PersonaVoice
from backend.scenarios import Scenario
from backend.session.language_packs import LANGUAGE_PACKS
from tests.conftest import load_seed_module

# _to_persona/_to_scenario are the mapping this module is about.
# pylint: disable=missing-function-docstring,protected-access
# pylint: disable=use-implicit-booleaness-not-comparison

SEED = load_seed_module()


# --- the mapping: database row -> value object --------------------------


_PERSONA_EXTERN_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


def _persona_row(**overrides):
    fields = {
        "key": "row-persona",
        "extern_id": _PERSONA_EXTERN_ID,
        "created_by": None,
        "visibility": models.VISIBILITY_PUBLIC,
        "name": "Thomas Brandt",
        "role_label": "Geschäftsführer, Fokus auf Strategie & Budget",
        "role": "Managing director of a mid-sized company",
        "traits": "matter-of-fact, time-conscious",
        "behavior": "You press for concrete answers.",
        "training_goal": "",
        "difficulty": "mittel",
        "language_code": "de",
        "tts_voice": "de_male",
        "kugelaudio_voice_id": 1885,
        "active": True,
        "language": models.Language(code="de", name="Deutsch"),
    }
    return models.Persona(**{**fields, **overrides})


def test_persona_row_maps_onto_the_value_object():
    """ADR 0041: the German column names stop at `library.py`; callers get a
    plain dataclass."""
    persona = _to_persona(_persona_row())
    assert isinstance(persona, Persona)
    # ADR 0058: the value object's id is the extern_id (what the client uses),
    # not the internal `key` slug.
    assert persona.id == str(_PERSONA_EXTERN_ID)
    assert persona.name == "Thomas Brandt"
    assert persona.role == "Managing director of a mid-sized company"
    assert persona.traits == "matter-of-fact, time-conscious"
    assert persona.behavior == "You press for concrete answers."


def test_persona_mapping_keeps_display_and_prompt_fields_apart():
    """ADR 0043: `role_label` is the card's label, `role` is prompt input.
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
    """ADR 0043: `short_description` is the teaser shown, `description` the
    English call context the model reads."""
    extern_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    scenario = _to_scenario(
        models.Scenario(
            key="row-scenario",
            extern_id=extern_id,
            created_by=None,
            visibility=models.VISIBILITY_PUBLIC,
            title="Kündigungsabsicht wegen Preis",
            short_description="Der Kunde erwägt zu kündigen.",
            description="The customer is calling to say they are considering cancelling.",
        )
    )
    assert isinstance(scenario, Scenario)
    assert scenario.id == str(extern_id)
    assert scenario.name == "Kündigungsabsicht wegen Preis"
    assert scenario.short_description == "Der Kunde erwägt zu kündigen."
    assert scenario.description.startswith("The customer")


# --- the seeded content -------------------------------------------------


def test_seeded_persona_library_is_non_empty_and_well_formed():
    assert SEED.PERSONAS, "F-04: the library ships at least one persona"
    for entry in SEED.PERSONAS:
        assert entry["id"] and entry["name"]
        assert entry["role"], "F-04: a persona carries a role"
        assert entry["role_label"], "ADR 0043: and a label to show on the card"
        assert entry["traits"], "F-01: a persona carries character traits"
        assert entry["behavior"], "F-01: a persona carries a behaviour description"


def test_seeded_persona_keys_are_unique():
    keys = [p["id"] for p in SEED.PERSONAS]
    assert len(keys) == len(set(keys))


def test_seeded_library_covers_the_budget_focused_decision_maker():
    """F-04 / R-08: a managing director or IT lead with a strategy & budget
    focus is representable. Asserted in English — ADR 0043 moved the prompt
    fields off German."""
    joined = " ".join(
        f"{p['role']} {p['traits']} {p['behavior']}".lower() for p in SEED.PERSONAS
    )
    assert "managing director" in joined or "it lead" in joined
    assert "budget" in joined or "strategy" in joined


def test_seeded_persona_behaviour_encodes_price_pushback():
    """F-04 / R-07: a cost-critical counterpart that presses on price."""
    joined = " ".join(p["behavior"].lower() for p in SEED.PERSONAS)
    assert "price" in joined


def test_seeded_scenario_library_is_non_empty_and_well_formed():
    assert SEED.SCENARIOS, "F-03: the library ships at least one scenario"
    for entry in SEED.SCENARIOS:
        assert entry["id"] and entry["name"]
        assert entry["short_description"], "ADR 0043: the card shows a teaser"
        assert len(entry["description"]) > 40, "the model gets a real call context"


def test_seeded_scenario_keys_are_unique():
    keys = [s["id"] for s in SEED.SCENARIOS]
    assert len(keys) == len(set(keys))


def test_seeded_scenarios_cover_support_and_pricing_contexts():
    """F-03 / R-09 / R-10: at least a support-style case and a
    price/cancellation negotiation are trainable."""
    blob = " ".join(f"{s['name']} {s['description']}".lower() for s in SEED.SCENARIOS)
    assert "support" in blob
    assert "cancel" in blob or "price" in blob


@pytest.mark.parametrize("entry", SEED.PERSONAS, ids=lambda e: e["id"])
def test_every_seeded_persona_speaks_a_language_that_has_a_pack(entry):
    """ADR 0043: a Persona's `language_code` decides the spoken language, and
    `get_pack` raises for one without a pack — a configuration error that
    would only surface once a Session starts."""
    assert entry["language_id"] in LANGUAGE_PACKS


@pytest.mark.parametrize("entry", SEED.PERSONAS, ids=lambda e: e["id"])
def test_every_offered_persona_has_its_own_voice(entry):
    """ADR 0040/0041: voice is a per-Persona property, and both backends need
    an identity — KugelAudio by default, the DiReKT model as fallback.

    A Persona still waiting for a KugelAudio voice is seeded `active: False`
    and is the one case where the id may be missing; the test below is what
    keeps that from turning into a Persona on offer that cannot speak."""
    assert entry["tts_voice"]
    if entry.get("active", True):
        assert isinstance(entry["kugelaudio_voice_id"], int)


@pytest.mark.parametrize("entry", SEED.PERSONAS, ids=lambda e: e["id"])
def test_a_seeded_persona_without_a_voice_is_not_offered(entry):
    """The converse, and the one that matters: `library.list_personas` filters
    on `active`, so an unfinished Persona is invisible — but only as long as
    nobody flips the flag before choosing the voice. Without the id the default
    TTS backend has nothing to synthesise with and every Turn falls through to
    the fallback model."""
    if entry["kugelaudio_voice_id"] is None:
        assert not entry.get("active", True), (
            f"{entry['id']}: on offer without a KugelAudio voice"
        )


def test_seeded_scenarios_carry_no_language_of_their_own():
    """ADR 0043: Scenarios stay language-neutral, which is what keeps every
    Persona x Scenario pairing valid (ADR 0001, ADR 0015)."""
    for entry in SEED.SCENARIOS:
        assert "language_id" not in entry
        assert "language" not in entry


# --- ADR 0045: the case on the Scenario, the objections on the Persona ---


def test_scenario_row_maps_the_case_fields():
    """ADR 0045: three columns, three fields — the case is addressable, not
    buried in the prose of `description`."""
    scenario = _to_scenario(
        models.Scenario(
            key="row-case",
            title="Kündigungsabsicht wegen Preis",
            short_description="Der Kunde erwägt zu kündigen.",
            description="The customer is calling to say they are considering cancelling.",
            case_facts="14 licences, 1,180 euros a month since March last year.",
            call_goal="Get the price down, or a clear reason why not.",
            success_condition="Settled once a specific figure with a date is committed to.",
        )
    )
    assert scenario.case_facts == "14 licences, 1,180 euros a month since March last year."
    assert scenario.call_goal == "Get the price down, or a clear reason why not."
    assert scenario.success_condition == (
        "Settled once a specific figure with a date is committed to."
    )


def test_persona_row_maps_its_objections_in_order():
    """R-12 / ADR 0026: the objections are ordered rows, and `position` is
    what orders them — `library.py` has to load and keep that order."""
    row = _persona_row(
        objections=[
            models.PersonaObjection(position=1, text="second objection"),
            models.PersonaObjection(position=0, text="first objection"),
        ]
    )
    persona = _to_persona(row)
    assert persona.objections == ("first objection", "second objection")


def test_persona_without_objections_maps_to_an_empty_tuple():
    """A Persona need not have objections; the prompt then omits the block."""
    # Specifically an empty *tuple* (ADR 0026), not just any falsey value.
    assert _to_persona(_persona_row(objections=[])).objections == ()


def test_objections_carry_no_language_of_their_own():
    """ADR 0043/0045: a Persona has a fixed language, and `persona_einwand` has
    no language column — which is why objections are authored in English, as
    moves rather than as quotable lines."""
    assert not hasattr(models.PersonaObjection, "language_code")
    assert not hasattr(models.PersonaObjection, "language")


def test_seeded_scenarios_carry_the_case():
    """ADR 0045: every shipped Scenario states its facts, the caller's goal and
    the condition under which the matter is settled."""
    for entry in SEED.SCENARIOS:
        assert entry["case_facts"].strip(), f"{entry['id']}: no case facts"
        assert entry["call_goal"].strip(), f"{entry['id']}: no call goal"
        assert entry["success_condition"].strip(), f"{entry['id']}: no success condition"


def test_seeded_scenario_context_does_not_carry_the_trainer_objective():
    """ADR 0045, the defect that prompted it: `description` used to end with
    what the *user* is meant to achieve ("keep the customer through price
    negotiation"), addressed to the Persona — who is the customer. The caller's
    own goal lives in `call_goal` now, and nothing hands it the trainee's."""
    for entry in SEED.SCENARIOS:
        lowered = entry["description"].lower()
        assert "the goal of the call is" not in lowered, entry["id"]
        assert "goal of the call" not in lowered, entry["id"]


def test_seeded_personas_carry_objections():
    """R-12: `persona_einwand` has been empty since ADR 0026 created it. Three
    to four per Persona is what ADR 0045 asks for."""
    for entry in SEED.PERSONAS:
        objections = entry["objections"]
        assert 3 <= len(objections) <= 4, f"{entry['id']}: {len(objections)} objections"
        assert all(text.strip() for text in objections)


def test_seeded_persona_behaviour_carries_no_situation():
    """ADR 0045: `behavior` is manner only. Both Personas used to open it with
    the same sentence about having a reason for the call — a statement about
    the Session's setup that the prompt frame already makes."""
    for entry in SEED.PERSONAS:
        lowered = entry["behavior"].lower()
        assert "reason for this call" not in lowered, entry["id"]
        assert "context of the call" not in lowered, entry["id"]


# --- ADR 0072: the category the library filter runs on ----------------------


def test_every_seeded_scenario_carries_a_valid_category():
    """ADR 0072: a shipped Scenario that no category filter finds is one nobody
    selects, and the value has to be one the CHECK constraint accepts."""
    for entry in SEED.SCENARIOS:
        assert entry["category"] in models.SCENARIO_CATEGORIES, entry["id"]


def test_the_seeded_library_fills_every_category():
    """F-03: short support cases, consultative project talks and pricing calls
    are each trainable, and no filter option is empty on a fresh install. Before
    the scenario catalogue landed, the consultative context had no Scenario at
    all."""
    assert {e["category"] for e in SEED.SCENARIOS} == set(models.SCENARIO_CATEGORIES)


def test_scenario_row_maps_its_category():
    """`library._to_scenario` carries the column onto the value object, which is
    what `/api/scenarios` badges the card from."""
    row = models.Scenario(
        key="row-category", title="t", short_description="s", description="d",
        case_facts="", call_goal="", success_condition="", category="requirements",
    )
    assert _to_scenario(row).category == "requirements"
    row.category = None
    assert _to_scenario(row).category is None


# --- ADR 0043: the prompt fields are English --------------------------------

# Two cheap signals that a German sentence slipped into a field the model reads
# as English. Neither is a language detector: the umlaut check is exact for the
# text this library actually contains, and the word list holds only forms that
# cannot also be English ("die", "man", "war", "will", "in", "so" are German
# words too and are deliberately absent).
_UMLAUTS = re.compile(r"[äöüÄÖÜß]")
_GERMAN_ONLY = re.compile(
    r"\b(ohne|nicht|und|oder|sind|wird|eine|einen|dass|sich|auch|aber|sehr|"
    r"kein|keine|wenn|weil|damit|schon|noch|nur|zwischen|werden|haben)\b",
    re.IGNORECASE,
)

# The four fields interpolated into the system prompt (ADR 0045). `name` and
# `short_description` are display text and stay German on purpose.
_PROMPT_FIELDS = ("description", "case_facts", "call_goal", "success_condition")


@pytest.mark.parametrize("entry", SEED.SCENARIOS, ids=lambda e: e["id"])
def test_seeded_scenario_prompt_fields_are_english(entry):
    """ADR 0043: a Scenario carries no language of its own, which is what lets
    any Persona run it. German in one of these fields would reach a Persona
    speaking English and is invisible until someone plays that pairing.

    This caught a real one: `call_goal` ended "...what it will cost, ohne
    Fachbegriffe" after an edit that was only meant to remove a dash.
    """
    for field in _PROMPT_FIELDS:
        text = entry[field]
        assert not _UMLAUTS.search(text), f"{entry['id']}.{field}: umlaut in an English field"
        found = _GERMAN_ONLY.search(text)
        assert found is None, f"{entry['id']}.{field}: German word {found.group()!r}"


@pytest.mark.parametrize("entry", SEED.PERSONAS, ids=lambda e: e["id"])
def test_seeded_persona_prompt_fields_are_english(entry):
    """Same for the Persona's prompt fields. `name` and `role_label` are display
    text; `training_goal` is not read by the model at all (see library.py) and
    is deliberately German."""
    for field in ("role", "traits", "behavior"):
        text = entry[field]
        assert not _UMLAUTS.search(text), f"{entry['id']}.{field}: umlaut in an English field"
        found = _GERMAN_ONLY.search(text)
        assert found is None, f"{entry['id']}.{field}: German word {found.group()!r}"


@pytest.mark.parametrize("entry", SEED.PERSONAS, ids=lambda e: e["id"])
def test_seeded_persona_objections_are_english(entry):
    """R-12 / ADR 0045: the objections are English moves, not quoted lines."""
    for text in entry["objections"]:
        assert not _UMLAUTS.search(text), f"{entry['id']}: umlaut in an objection"
        assert _GERMAN_ONLY.search(text) is None, f"{entry['id']}: German in an objection"
