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

R-12 (spontaneous objections) is *not* covered here: no objection is fed into
the prompt yet. `test_documented_gaps.py` guards that gap until ADR 0045 lands.
"""

import pytest

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
    """ADR 0043: the English `rolle` goes to the model; `rolle_anzeige` is for
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
