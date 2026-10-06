"""The library mapping and seed content (F-01, F-03, F-04, F-44, R-07-R-12, ADR 0041, 0043, 0045)."""

import pathlib
import re
import uuid

import pytest

from shared.db import models
from shared.language_packs import LANGUAGE_PACKS
from backend.library import _to_persona, _to_scenario
from backend.personas import Persona, PersonaVoice
from backend.scenarios import Scenario
from backend.tests.conftest import load_seed_module

# pylint: disable=missing-function-docstring,use-implicit-booleaness-not-comparison

SEED = load_seed_module()


_PERSONA_EXTERN_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


def _persona_row(**overrides):
    fields = {
        "key": "row-persona",
        "extern_id": _PERSONA_EXTERN_ID,
        "name": "Thomas Brandt",
        "role_label": "Geschäftsführer, Fokus auf Strategie & Budget",
        "role": "Managing director of a mid-sized company",
        "traits": "matter-of-fact, time-conscious",
        "behavior": "You press for concrete answers.",
        "training_goal": "",
        "language_code": "de",
        "kugelaudio_voice_id": 1885,
        "active": True,
        "language": models.Language(code="de", name="Deutsch"),
    }
    return models.Persona(**{**fields, **overrides})


def test_persona_row_maps_onto_the_value_object():
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
    persona = _to_persona(_persona_row())
    assert persona.role_label == "Geschäftsführer, Fokus auf Strategie & Budget"
    assert persona.role != persona.role_label


def test_persona_mapping_carries_language_and_both_voices():
    persona = _to_persona(_persona_row())
    assert persona.language_id == "de"
    assert persona.language_name == "Deutsch"
    assert isinstance(persona.voice, PersonaVoice)
    assert persona.voice.kugelaudio_voice_id == 1885


def test_scenario_row_maps_onto_the_value_object():
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
    joined = " ".join(
        f"{p['role']} {p['traits']} {p['behavior']}".lower() for p in SEED.PERSONAS
    )
    assert "managing director" in joined or "it lead" in joined
    assert "budget" in joined or "strategy" in joined


def test_seeded_persona_behaviour_encodes_price_pushback():
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
    blob = " ".join(f"{s['name']} {s['description']}".lower() for s in SEED.SCENARIOS)
    assert "support" in blob
    assert "cancel" in blob or "price" in blob


@pytest.mark.parametrize("entry", SEED.PERSONAS, ids=lambda e: e["id"])
def test_every_seeded_persona_speaks_a_language_that_has_a_pack(entry):
    assert entry["language_id"] in LANGUAGE_PACKS


@pytest.mark.parametrize("entry", SEED.PERSONAS, ids=lambda e: e["id"])
def test_every_offered_persona_has_its_own_voice(entry):
    if entry.get("active", True):
        assert isinstance(entry["kugelaudio_voice_id"], int)


@pytest.mark.parametrize("entry", SEED.PERSONAS, ids=lambda e: e["id"])
def test_a_seeded_persona_without_a_voice_is_not_offered(entry):
    if entry["kugelaudio_voice_id"] is None:
        assert not entry.get("active", True), (
            f"{entry['id']}: on offer without a KugelAudio voice"
        )


def test_seeded_scenarios_carry_no_language_of_their_own():
    for entry in SEED.SCENARIOS:
        assert "language_id" not in entry
        assert "language" not in entry


def test_scenario_row_maps_the_case_fields():
    scenario = _to_scenario(
        models.Scenario(
            key="row-case",
            title="Kündigungsabsicht wegen Preis",
            short_description="Der Kunde erwägt zu kündigen.",
            description="The customer is calling to say they are considering cancelling.",
            case_facts="14 licences, 1,180 euros a month since March last year.",
            call_goal=(
                "Get the price down, or a clear reason why not. Settled once a "
                "specific figure with a date is committed to."
            ),
        )
    )
    assert scenario.case_facts == "14 licences, 1,180 euros a month since March last year."
    assert scenario.call_goal == (
        "Get the price down, or a clear reason why not. Settled once a "
        "specific figure with a date is committed to."
    )


def test_persona_row_maps_its_objections_in_order():
    row = _persona_row(
        objections=[
            models.PersonaObjection(position=1, text="second objection"),
            models.PersonaObjection(position=0, text="first objection"),
        ]
    )
    persona = _to_persona(row)
    assert persona.objections == ("first objection", "second objection")


def test_persona_without_objections_maps_to_an_empty_tuple():
    # Specifically an empty *tuple* (ADR 0026), not just any falsey value.
    assert _to_persona(_persona_row(objections=[])).objections == ()


def test_objections_carry_no_language_of_their_own():
    assert not hasattr(models.PersonaObjection, "language_code")
    assert not hasattr(models.PersonaObjection, "language")


def test_seeded_scenarios_carry_the_case():
    for entry in SEED.SCENARIOS:
        assert entry["case_facts"].strip(), f"{entry['id']}: no case facts"
        assert entry["call_goal"].strip(), f"{entry['id']}: no call goal"


def test_seeded_scenario_context_does_not_carry_the_trainer_objective():
    for entry in SEED.SCENARIOS:
        lowered = entry["description"].lower()
        assert "the goal of the call is" not in lowered, entry["id"]
        assert "goal of the call" not in lowered, entry["id"]


def test_seeded_personas_carry_objections():
    for entry in SEED.PERSONAS:
        objections = entry["objections"]
        assert 3 <= len(objections) <= 4, f"{entry['id']}: {len(objections)} objections"
        assert all(text.strip() for text in objections)


@pytest.mark.parametrize("entry", SEED.PERSONAS, ids=lambda e: e["id"])
def test_seeded_persona_carries_german_display_text(entry):
    assert entry["traits_label"].strip(), f"{entry['id']}: no traits_label"
    # Checks the display field was written, not copied off its prompt twin.
    assert entry["traits_label"] != entry["traits"], f"{entry['id']}: traits_label is the prompt text"


@pytest.mark.parametrize("entry", SEED.PERSONAS, ids=lambda e: e["id"])
def test_every_objection_has_exactly_one_german_label(entry):
    labels = entry["objection_labels"]
    assert len(labels) == len(entry["objections"]), entry["id"]
    assert all(label.strip() for label in labels), entry["id"]


@pytest.mark.parametrize("entry", SEED.SCENARIOS, ids=lambda e: e["id"])
def test_seeded_scenario_carries_german_display_text(entry):
    for field in ("description_label", "case_facts_label"):
        assert entry[field].strip(), f"{entry['id']}: no {field}"
        assert entry[field] != entry[field.removesuffix("_label")], (
            f"{entry['id']}: {field} is the prompt text"
        )


@pytest.mark.parametrize("entry", SEED.SCENARIOS, ids=lambda e: e["id"])
def test_seeded_scenario_display_text_carries_no_dash(entry):
    for field in ("name", "short_description", "briefing",
                  "description_label", "case_facts_label"):
        assert not _DISPLAY_DASH.search(entry[field] or ""), (
            f"{entry['id']}.{field}: dash in display text"
        )


def test_seeded_persona_behaviour_carries_no_situation():
    for entry in SEED.PERSONAS:
        lowered = entry["behavior"].lower()
        assert "reason for this call" not in lowered, entry["id"]
        assert "context of the call" not in lowered, entry["id"]


def test_every_seeded_scenario_carries_a_valid_category():
    for entry in SEED.SCENARIOS:
        assert entry["category"] in models.SCENARIO_CATEGORIES, entry["id"]


def test_the_seeded_library_fills_every_category():
    assert {e["category"] for e in SEED.SCENARIOS} == set(models.SCENARIO_CATEGORIES)


def test_scenario_row_maps_its_category():
    row = models.Scenario(
        key="row-category", title="t", short_description="s", description="d",
        case_facts="", call_goal="", category="requirements",
    )
    assert _to_scenario(row).category == "requirements"
    row.category = None
    assert _to_scenario(row).category is None


# Cheap signals of German in an English field. The word list holds only forms
# that cannot also be English.
_UMLAUTS = re.compile(r"[äöüÄÖÜß]")
# An em or en dash with space around it: the joiner this seed used to reach
# for. A hyphen inside a compound ("IT-Seite") is not one and must pass.
_DISPLAY_DASH = re.compile(r"\s[—–]\s")
_GERMAN_ONLY = re.compile(
    r"\b(ohne|nicht|und|oder|sind|wird|eine|einen|dass|sich|auch|aber|sehr|"
    r"kein|keine|wenn|weil|damit|schon|noch|nur|zwischen|werden|haben)\b",
    re.IGNORECASE,
)

# The three fields interpolated into the system prompt (ADR 0045). `name` and
# `short_description` are display text and stay German on purpose.
_PROMPT_FIELDS = ("description", "case_facts", "call_goal")


@pytest.mark.parametrize("entry", SEED.SCENARIOS, ids=lambda e: e["id"])
def test_seeded_scenario_prompt_fields_are_english(entry):
    for field in _PROMPT_FIELDS:
        text = entry[field]
        assert not _UMLAUTS.search(text), f"{entry['id']}.{field}: umlaut in an English field"
        found = _GERMAN_ONLY.search(text)
        assert found is None, f"{entry['id']}.{field}: German word {found.group()!r}"


@pytest.mark.parametrize("entry", SEED.PERSONAS, ids=lambda e: e["id"])
def test_seeded_persona_prompt_fields_are_english(entry):
    for field in ("role", "traits", "behavior"):
        text = entry[field]
        assert not _UMLAUTS.search(text), f"{entry['id']}.{field}: umlaut in an English field"
        found = _GERMAN_ONLY.search(text)
        assert found is None, f"{entry['id']}.{field}: German word {found.group()!r}"


@pytest.mark.parametrize("entry", SEED.PERSONAS, ids=lambda e: e["id"])
def test_seeded_persona_objections_are_english(entry):
    for text in entry["objections"]:
        assert not _UMLAUTS.search(text), f"{entry['id']}: umlaut in an objection"
        assert _GERMAN_ONLY.search(text) is None, f"{entry['id']}: German in an objection"


# The portrait pairing lives in two places and can drift silently.
_PORTRAIT_DIR = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "public" / "personas"


@pytest.mark.parametrize("entry", SEED.PERSONAS, ids=lambda e: e["id"])
def test_every_seeded_persona_carries_a_portrait_named_after_it(entry):
    slug = entry["name"].lower().replace(" ", "-")
    assert entry["avatar_url"] == f"/personas/{slug}.webp"


@pytest.mark.parametrize("entry", SEED.PERSONAS, ids=lambda e: e["id"])
def test_every_seeded_portrait_is_a_file_that_exists(entry):
    served = _PORTRAIT_DIR / pathlib.PurePosixPath(entry["avatar_url"]).name
    assert served.is_file(), f"{entry['id']}: no portrait at {entry['avatar_url']}"


# One over-long seed value rolls back the whole seed and /api/scenarios 500s.
# Mirrors `provision._seed_*`.
_PERSONA_COLUMNS = {
    "id": "key", "name": "name", "role_label": "role_label", "role": "role",
    "traits": "traits", "avatar_url": "avatar_url",
    "language_id": "language_code",
}
_SCENARIO_COLUMNS = {
    "id": "key", "name": "title", "short_description": "short_description",
    "briefing": "briefing", "description": "description",
    "case_facts": "case_facts", "call_goal": "call_goal",
    "category": "category",
}


def _too_long(model, field_to_column, entry):
    """Every seeded value that is longer than its column allows."""
    for field, column in field_to_column.items():
        value = entry.get(field)
        limit = getattr(model.__table__.c[column].type, "length", None)
        if value is None or limit is None:
            continue
        if len(value) > limit:
            yield f"{field} -> {model.__tablename__}.{column}: {len(value)} > {limit}"


@pytest.mark.parametrize("entry", SEED.PERSONAS, ids=lambda e: e["id"])
def test_seeded_persona_fits_the_columns_it_is_written_into(entry):
    over = list(_too_long(models.Persona, _PERSONA_COLUMNS, entry))
    assert not over, f"{entry['id']}: " + "; ".join(over)


@pytest.mark.parametrize("entry", SEED.SCENARIOS, ids=lambda e: e["id"])
def test_seeded_scenario_fits_the_columns_it_is_written_into(entry):
    over = list(_too_long(models.Scenario, _SCENARIO_COLUMNS, entry))
    assert not over, f"{entry['id']}: " + "; ".join(over)
