"""The system prompt (F-01, F-03, F-04, F-12, R-12, ADR 0037, 0038, 0043, 0045)."""

from dataclasses import replace

import pytest

from shared.language_packs import get_pack
from backend.scenarios import Scenario
from backend.session.prompting import build_system_prompt, opening_instruction
from backend.tests.conftest import TEST_PERSONAS, TEST_SCENARIOS

# build_system_prompt is the unit under test here.
# pylint: disable=missing-function-docstring,redefined-outer-name

GERMAN = get_pack("de")


@pytest.fixture
def prompt(persona, scenario):
    return build_system_prompt(persona, scenario, GERMAN)


def test_prompt_injects_scenario_context(prompt):
    assert TEST_SCENARIOS[0].description in prompt


def test_prompt_injects_persona_name_role_traits_and_behaviour(prompt, persona):
    assert persona.name in prompt
    assert persona.role in prompt
    assert persona.traits in prompt
    assert persona.behavior in prompt


def test_prompt_serves_prompt_fields_not_display_fields(prompt, persona):
    assert persona.role_label not in prompt


def test_prompt_puts_the_persona_in_the_calling_role(prompt):
    lowered = prompt.lower()
    assert "you are the one who called" in lowered
    assert "never ask the user what their question or" in lowered


def test_prompt_asks_for_improvised_specifics(prompt):
    lowered = prompt.lower()
    assert "invent" in lowered and "plausible" in lowered


def test_prompt_forbids_repeating_itself(prompt):
    assert "Never repeat yourself" in prompt


def test_prompt_forbids_re_introducing_after_the_opening(prompt):
    lowered = prompt.lower()
    assert "do not greet the user again" in lowered
    assert "do not give your name again" in lowered


def test_prompt_takes_the_spoken_language_from_the_persona(persona, scenario):
    german = build_system_prompt(persona, scenario, GERMAN)
    english = build_system_prompt(persona, scenario, get_pack("en"))
    assert "Reply exclusively in German" in german
    assert "Reply exclusively in English" in english
    assert "regardless of what language the user writes in" in german


def test_prompt_carries_the_language_packs_example_exchange(prompt):
    assert GERMAN.example_exchange in prompt


def test_prompt_forbids_meta_commentary_and_stage_directions(prompt):
    lowered = prompt.lower()
    assert "no meta-commentary" in lowered
    assert "no stage directions" in lowered


def test_prompt_defines_the_call_end_marker_protocol(prompt):
    assert "[CALL_END]" in prompt
    assert "Never end the call while your concern is still unresolved" in prompt
    assert "unresolved" in prompt


def test_authored_scenario_gets_the_content_note_a_built_in_does_not(persona):
    built_in = build_system_prompt(persona, TEST_SCENARIOS[0], GERMAN)
    authored = build_system_prompt(
        persona, replace(TEST_SCENARIOS[0], created_by="alice"), GERMAN
    )
    note = "were written by whoever set up this training exercise"
    assert note not in built_in
    assert note in authored
    # The case facts themselves are still handed over plainly, no <<< >>> wrapper.
    prompt = build_system_prompt(persona, _case_scenario(created_by="alice"), GERMAN)
    assert "<<<" not in prompt
    assert _case_scenario().case_facts in prompt


def test_prompt_is_rebuilt_per_persona_scenario_pair(persona):
    a = build_system_prompt(persona, TEST_SCENARIOS[0], GERMAN)
    b = build_system_prompt(persona, TEST_SCENARIOS[1], GERMAN)
    assert a != b
    assert TEST_SCENARIOS[1].description in b


def test_every_persona_can_run_every_scenario():
    for persona in TEST_PERSONAS:
        for scenario in TEST_SCENARIOS:
            built = build_system_prompt(persona, scenario, get_pack(persona.language_id))
            assert scenario.description in built
            assert persona.role in built


def testopening_instruction_offers_several_openers_from_the_language_pack():
    """ADR 0043: a single English example was copied verbatim into every call,
    German ones included — so the openers are per-language and plural."""
    instruction = opening_instruction(GERMAN)
    assert GERMAN.opening_examples in instruction
    assert len(GERMAN.opening_examples.splitlines()) > 1
    assert "Do not reuse" in instruction


def test_the_ordinary_opening_answers_the_users_pickup():
    instruction = opening_instruction(GERMAN)
    assert "the user has just picked up" in instruction
    assert "does not apply to this reply" in instruction


def testopening_instruction_keeps_the_background_out_of_the_opening():
    instruction = opening_instruction(GERMAN)
    assert "Name the reason in a clause, not in a summary" in instruction
    assert "one piece at a time" in instruction


# Situation on the Scenario, manner on the Persona: two Personas on one Scenario
# get the same facts and differ only in how they push back.


def _case_scenario(**overrides):
    """A Scenario carrying the case ADR 0045 puts on it."""
    fields = {
        "id": "test-scenario-case",
        "name": "Kündigungsabsicht wegen Preis",
        "short_description": "Der Kunde erwägt zu kündigen, weil die Kosten zu hoch sind.",
        "description": (
            "The customer (the persona) is calling to say they are considering "
            "cancelling, because the running costs seem too high for the benefit."
        ),
        "case_facts": (
            'Package "Insight Analytics", 14 licences, 1,180 euros a month, running '
            "since March last year. The last renewal raised it by 12 percent, from "
            "1,050 euros. Two of its six modules are in use."
        ),
        "call_goal": (
            "Get the price down, or get a clear reason why not. Cancelling is a "
            "real option and one you say out loud. The matter is settled once a "
            "specific figure with a date has been committed to. "
            '"I will look into it" is not enough.'
        ),
    }
    return Scenario(**{**fields, **overrides})


OBJECTIONS = (
    "pushes back that the figure is above what was budgeted",
    "points out this was promised once before and nothing came of it",
    "asks what the two unused modules are being paid for",
)


def test_prompt_carries_the_case_facts(persona):
    scenario = _case_scenario()
    prompt = build_system_prompt(persona, scenario, GERMAN)
    assert scenario.case_facts in prompt
    assert "Facts of the case" in prompt


def test_prompt_carries_the_call_goal(persona):
    scenario = _case_scenario()
    prompt = build_system_prompt(persona, scenario, GERMAN)
    assert scenario.call_goal in prompt
    assert "What you want from this call" in prompt


def test_prompt_carries_the_settlement_bar(persona):
    scenario = _case_scenario()
    prompt = build_system_prompt(persona, scenario, GERMAN)
    assert scenario.call_goal in prompt
    assert "when you count the matter settled" in prompt


def test_prompt_never_carries_the_trainees_briefing(persona):
    marker = "Sie sitzen im Vertrieb und duerfen bis zehn Prozent nachlassen."
    prompt = build_system_prompt(persona, _case_scenario(briefing=marker), GERMAN)

    assert marker not in prompt
    # Not just the text: no wording of the field leaks in either.
    assert "briefing" not in prompt.lower()


def test_prompt_binds_the_model_to_the_case_facts(persona):
    prompt = build_system_prompt(persona, _case_scenario(), GERMAN)
    lowered = prompt.lower()
    assert "invent only what they leave open" in lowered
    assert "never contradict" in lowered


def test_prompt_falls_back_to_improvisation_without_case_facts(persona):
    prompt = build_system_prompt(persona, _case_scenario(case_facts=""), GERMAN)
    lowered = prompt.lower()
    assert "concrete, plausible details" in lowered
    assert "facts of the case" not in lowered


def test_prompt_lists_the_personas_objections(persona):
    with_objections = replace(persona, objections=OBJECTIONS)
    prompt = build_system_prompt(with_objections, _case_scenario(), GERMAN)
    for objection in OBJECTIONS:
        assert objection in prompt


def test_prompt_limits_objections_to_one_per_reply(persona):
    with_objections = replace(persona, objections=OBJECTIONS)
    prompt = build_system_prompt(with_objections, _case_scenario(), GERMAN)
    lowered = prompt.lower()
    assert "at most one" in lowered
    assert "never work through them as a list" in lowered


def test_prompt_omits_the_objection_block_for_a_persona_without_objections(persona):
    prompt = build_system_prompt(replace(persona, objections=()), _case_scenario(), GERMAN)
    assert "Objections you tend to raise" not in prompt


def test_the_case_is_identical_for_every_persona_running_the_scenario():
    scenario = _case_scenario()
    for persona in TEST_PERSONAS:
        prompt = build_system_prompt(persona, scenario, get_pack(persona.language_id))
        assert scenario.case_facts in prompt
        assert scenario.call_goal in prompt


def test_prompt_puts_the_satisfaction_check_before_every_reply(prompt):
    assert "Before every reply, check first whether what you came for has" in prompt
    lowered = prompt.lower()
    assert "do not ask again to make sure" in lowered
    assert "accept it out loud in your own words" in lowered


def test_prompt_credits_a_commitment_given_piece_by_piece(prompt):
    lowered = prompt.lower()
    assert "piece by piece" in lowered
    assert "had to ask twice" in lowered


def test_prompt_keeps_the_guard_against_ending_too_early(prompt):
    assert "Never end the call while your concern is still unresolved" in prompt
    assert "vague reassurance with no specifics" in prompt


def test_prompt_forbids_reciting_the_whole_case(persona):
    prompt = build_system_prompt(persona, _case_scenario(), GERMAN)
    lowered = prompt.lower()
    assert "at most one or two of them in a single reply" in lowered
    assert "never the whole case at once" in lowered


def test_prompt_forbids_re_asking_an_answered_question(prompt):
    lowered = prompt.lower()
    assert "already answered is the same mistake" in lowered


def test_settlement_bar_is_a_criterion_not_a_line_to_recite(persona):
    prompt = build_system_prompt(persona, _case_scenario(), GERMAN)
    lowered = prompt.lower()
    assert "check silently, never to read out" in lowered
    assert "never restate a demand you have already made" in lowered


def test_prompt_tells_the_model_the_date(persona, scenario):
    from datetime import date  # pylint: disable=import-outside-toplevel

    prompt = build_system_prompt(persona, scenario, GERMAN, today=date(2026, 9, 6))
    assert "Today is Sunday, 06 September 2026." in prompt


def test_prompt_repeats_the_language_rule_where_the_case_is(persona):
    with_case = build_system_prompt(persona, _case_scenario(), GERMAN).lower()
    assert "no english words carried over" in with_case
    assert "entirely in german" in with_case
    bare = build_system_prompt(persona, _case_scenario(case_facts="", call_goal=""), GERMAN).lower()
    assert "no english words carried over" not in bare


def test_no_usage_rule_without_a_call_goal(persona):
    prompt = build_system_prompt(persona, _case_scenario(call_goal=""), GERMAN)
    assert "check silently" not in prompt.lower()
