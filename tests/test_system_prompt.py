"""The LLM system prompt the orchestrator builds for a session.

This is where most functional requirements about *how the counterpart
behaves* are actually implemented, so they are asserted against the prompt
text.

Covers:
  F-01  live simulation: reacts to content and conversation management
  F-04  persona role/traits/behaviour is injected
  F-03  scenario context is injected
  F-12  the persona speaks only its lines, no meta-commentary (transcript
        stays clean)
  ADR 0043  instructions are English; the spoken language comes from the
            Persona, and what cannot follow into English lives in the
            language pack
  ADR 0033 / ADR 0037 / ADR 0038  the [CALL_END] closing protocol
  ADR 0045  the Scenario carries the case (facts, call goal, success
            condition), the Persona carries the objections
  R-12  spontaneous objections
"""

from dataclasses import replace

import pytest

from backend.scenarios import Scenario
from backend.session.language_packs import get_pack
from backend.session.orchestrator import _build_system_prompt, _opening_instruction
from tests.conftest import TEST_PERSONAS, TEST_SCENARIOS

# _build_system_prompt is the unit under test here.
# pylint: disable=missing-function-docstring,redefined-outer-name,protected-access

GERMAN = get_pack("de")


@pytest.fixture
def prompt(persona, scenario):
    return _build_system_prompt(persona, scenario, GERMAN)


def test_prompt_injects_scenario_context(prompt):
    """F-03: the chosen scenario's description is part of the persona's brief."""
    assert TEST_SCENARIOS[0].description in prompt


def test_prompt_injects_persona_name_role_traits_and_behaviour(prompt, persona):
    """F-04: the persona's role, traits and behaviour drive the character, and
    it introduces itself by its own name rather than inventing one."""
    assert persona.name in prompt
    assert persona.role in prompt
    assert persona.traits in prompt
    assert persona.behavior in prompt


def test_prompt_serves_prompt_fields_not_display_fields(prompt, persona):
    """ADR 0043: the English `role` goes to the model; `role_label` is for
    the selection card and has no business in the prompt."""
    assert persona.role_label not in prompt


def test_prompt_puts_the_persona_in_the_calling_role(prompt):
    """F-01: the persona initiated the call and drives it — it must not wait
    for the user to explain why they are calling."""
    lowered = prompt.lower()
    assert "you are the one who called" in lowered
    assert "never ask the user what their question or" in lowered


def test_prompt_asks_for_improvised_specifics(prompt):
    """F-01: the counterpart improvises concrete details rather than reading a
    scripted FAQ."""
    lowered = prompt.lower()
    assert "invent" in lowered and "plausible" in lowered


def test_prompt_forbids_repeating_itself(prompt):
    """ADR 0038: degenerate repetition is the failure this frame works hardest
    against, so the instruction is explicit."""
    assert "Never repeat yourself" in prompt


def test_prompt_takes_the_spoken_language_from_the_persona(persona, scenario):
    """ADR 0043: instructions are English, and only the Persona's language pack
    decides what the model speaks."""
    german = _build_system_prompt(persona, scenario, GERMAN)
    english = _build_system_prompt(persona, scenario, get_pack("en"))
    assert "Reply exclusively in German" in german
    assert "Reply exclusively in English" in english
    assert "regardless of what language the user writes in" in german


def test_prompt_carries_the_language_packs_example_exchange(prompt):
    """ADR 0043: the example demonstrates the register of a call in the target
    language, so it is the one illustrative block that is not English."""
    assert GERMAN.example_exchange in prompt


def test_prompt_forbids_meta_commentary_and_stage_directions(prompt):
    """F-12: only spoken persona lines, so the post-call transcript is clean."""
    lowered = prompt.lower()
    assert "no meta-commentary" in lowered
    assert "no stage directions" in lowered


def test_prompt_defines_the_call_end_marker_protocol(prompt):
    """ADR 0033/0037/0038: the persona ends the call itself by emitting
    [CALL_END], and only when the call should truly end."""
    assert "[CALL_END]" in prompt
    assert "Never end the call while you still consider your concern" in prompt
    assert "unresolved" in prompt


def test_prompt_is_rebuilt_per_persona_scenario_pair(persona):
    """ADR 0001: every persona x scenario combination yields its own prompt."""
    a = _build_system_prompt(persona, TEST_SCENARIOS[0], GERMAN)
    b = _build_system_prompt(persona, TEST_SCENARIOS[1], GERMAN)
    assert a != b
    assert TEST_SCENARIOS[1].description in b


def test_every_persona_can_run_every_scenario():
    """ADR 0001/0015: no pairing is invalid, and ADR 0043 keeps it that way by
    leaving Scenarios language-neutral."""
    for persona in TEST_PERSONAS:
        for scenario in TEST_SCENARIOS:
            built = _build_system_prompt(persona, scenario, get_pack(persona.language_id))
            assert scenario.description in built
            assert persona.role in built


def test_opening_instruction_offers_several_openers_from_the_language_pack():
    """ADR 0043: a single English example was copied verbatim into every call,
    German ones included — so the openers are per-language and plural."""
    instruction = _opening_instruction(GERMAN)
    assert GERMAN.opening_examples in instruction
    assert len(GERMAN.opening_examples.splitlines()) > 1
    assert "Do not reuse" in instruction


# --- ADR 0045: the case on the Scenario, the objections on the Persona ---
#
# The faustregel these tests encode: the situation belongs to the Scenario and
# the manner to the Persona, so both Personas running one Scenario get the same
# facts, goal and success condition, and differ only in how they push back.


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
            "real option and one you say out loud."
        ),
        "success_condition": (
            "Settled once a specific figure with a date has been committed to. "
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
    """ADR 0045: the case stops being improvised — the facts are handed to the
    model instead of invented anew every Session."""
    scenario = _case_scenario()
    prompt = _build_system_prompt(persona, scenario, GERMAN)
    assert scenario.case_facts in prompt
    assert "Facts of the case" in prompt


def test_prompt_carries_the_call_goal(persona):
    """ADR 0045: what the *caller* wants, in the caller's own terms — not the
    trainee's objective."""
    scenario = _case_scenario()
    prompt = _build_system_prompt(persona, scenario, GERMAN)
    assert scenario.call_goal in prompt
    assert "What you want from this call" in prompt


def test_prompt_carries_the_success_condition(persona):
    """ADR 0045: the observable condition under which the caller considers the
    matter settled — the criterion [CALL_END] can be weighed against."""
    scenario = _case_scenario()
    prompt = _build_system_prompt(persona, scenario, GERMAN)
    assert scenario.success_condition in prompt
    assert "settled when" in prompt


def test_prompt_binds_the_model_to_the_case_facts(persona):
    """ADR 0045: with facts present, improvisation is bounded — fill the gaps,
    never overwrite what the case already states."""
    prompt = _build_system_prompt(persona, _case_scenario(), GERMAN)
    lowered = prompt.lower()
    assert "invent only what they leave open" in lowered
    assert "never contradict" in lowered


def test_prompt_falls_back_to_improvisation_without_case_facts(persona):
    """ADR 0045 / ADR 0024: a Scenario without facts — a user-authored one, say
    — keeps the old instruction, because there is nothing to point the model
    at."""
    prompt = _build_system_prompt(persona, _case_scenario(case_facts=""), GERMAN)
    lowered = prompt.lower()
    assert "concrete, plausible details" in lowered
    assert "facts of the case" not in lowered


def test_prompt_lists_the_personas_objections(persona):
    """R-12 / ADR 0045: `persona_einwand` finally reaches the call."""
    with_objections = replace(persona, objections=OBJECTIONS)
    prompt = _build_system_prompt(with_objections, _case_scenario(), GERMAN)
    for objection in OBJECTIONS:
        assert objection in prompt


def test_prompt_limits_objections_to_one_per_reply(persona):
    """ADR 0045: quoted examples get parroted and lists get worked through, so
    the frame has to say how the objections are meant to be used."""
    with_objections = replace(persona, objections=OBJECTIONS)
    prompt = _build_system_prompt(with_objections, _case_scenario(), GERMAN)
    lowered = prompt.lower()
    assert "at most one" in lowered
    assert "never work through them as a list" in lowered


def test_prompt_omits_the_objection_block_for_a_persona_without_objections(persona):
    """A Persona with no objections must not get an empty heading."""
    prompt = _build_system_prompt(replace(persona, objections=()), _case_scenario(), GERMAN)
    assert "Objections you tend to raise" not in prompt


def test_the_case_is_identical_for_every_persona_running_the_scenario():
    """ADR 0045's faustregel, and what keeps ADR 0001/0015 intact: the Scenario
    supplies the situation, the Persona only the manner. Both Personas get the
    same facts, goal and condition."""
    scenario = _case_scenario()
    for persona in TEST_PERSONAS:
        prompt = _build_system_prompt(persona, scenario, get_pack(persona.language_id))
        assert scenario.case_facts in prompt
        assert scenario.call_goal in prompt
        assert scenario.success_condition in prompt
