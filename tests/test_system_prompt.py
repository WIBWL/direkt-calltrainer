"""The LLM system prompt the orchestrator builds for a session.

This is where most functional requirements about *how the counterpart
behaves* are actually implemented, so they are asserted against the prompt
text.

Covers:
  F-01  live simulation: reacts to content and conversation management,
        including spontaneous objections (R-12)
  F-04  persona attitude/role is injected
  F-03  scenario context is injected
  F-12  the persona speaks only its lines, no meta-commentary (transcript
        stays clean)
  ADR 0006  replies are German-only, regardless of the user's language
  ADR 0033 / ADR 0037 / ADR 0038  the [CALL_END] closing protocol
"""

import pytest

from backend.personas import PERSONAS
from backend.scenarios import SCENARIOS
from backend.session.orchestrator import _build_system_prompt

# pylint: disable=missing-function-docstring,redefined-outer-name


@pytest.fixture
def prompt():
    return _build_system_prompt(PERSONAS[0], SCENARIOS[0])


def test_prompt_injects_scenario_context(prompt):
    """F-03: the chosen scenario's description is part of the persona's brief."""
    assert SCENARIOS[0].description in prompt


def test_prompt_injects_persona_role_traits_and_behaviour(prompt):
    """F-04: the persona's role, traits and behaviour drive the character."""
    assert PERSONAS[0].role in prompt
    assert PERSONAS[0].traits in prompt
    assert PERSONAS[0].behavior in prompt


def test_prompt_puts_the_persona_in_the_calling_role(prompt):
    """F-01: the persona initiated the call and drives it — it must not wait
    for the user to explain why they are calling."""
    lowered = prompt.lower()
    assert "you are the one who called" in lowered
    assert "never ask the user what their question or" in lowered


def test_prompt_asks_for_improvised_specifics_and_objections(prompt):
    """F-01 / R-12: the counterpart improvises concrete details and raises
    objections rather than reading a scripted FAQ."""
    lowered = prompt.lower()
    assert "invent" in lowered and "plausible" in lowered
    assert "objection" in lowered


def test_prompt_forces_german_replies(prompt):
    """ADR 0006: reply in German every time regardless of the user's language."""
    assert "Reply exclusively in German" in prompt
    assert "regardless of what language the user writes in" in prompt


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


def test_prompt_is_rebuilt_per_persona_scenario_pair():
    """ADR 0001: every persona x scenario combination yields its own prompt."""
    a = _build_system_prompt(PERSONAS[0], SCENARIOS[0])
    b = _build_system_prompt(PERSONAS[0], SCENARIOS[1])
    assert a != b
    assert SCENARIOS[1].description in b
