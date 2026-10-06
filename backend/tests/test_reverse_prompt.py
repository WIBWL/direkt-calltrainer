"""The reverse's swapped casting, and that an ordinary prompt carries none of it (F-61, ADR 0070)."""

from dataclasses import replace

import pytest

from shared.language_packs import get_pack
from backend.session.nudges import (
    ANTI_REPEAT_NUDGE, ANTI_REPEAT_NUDGE_REVERSE, SETTLEMENT_CHECK_REVERSE,
)
from backend.session.orchestrator import SessionOrchestrator
from backend.session.prompting import (
    build_state_prompt, build_system_prompt, opening_instruction,
)
from backend.tests.conftest import TEST_PERSONAS, TEST_SCENARIOS

# The builders are the unit under test.
# pylint: disable=missing-function-docstring,redefined-outer-name

GERMAN = get_pack("de")

# A case on both, so the reverse block has both fields to turn around.
_CASE = {
    "case_facts": "A ticket was opened eleven days ago; a callback was promised.",
    "call_goal": (
        "Find out what is happening and get a date. The matter is settled when "
        "someone names one. A promise to look into it is not enough."
    ),
}


@pytest.fixture
def persona():
    # The one with objections, so dropping them in a reverse is observable.
    return replace(TEST_PERSONAS[0], objections=("The price is too high", "No time this quarter"))


@pytest.fixture
def played():
    """An ordinary Scenario, with a case."""
    return replace(TEST_SCENARIOS[0], **_CASE)


@pytest.fixture
def reversed_scenario(played):
    """The same case, marked as a reverse — which is all a reverse row is."""
    return replace(played, reverse=True)


@pytest.fixture
def prompt(persona, reversed_scenario):
    return build_system_prompt(persona, reversed_scenario, GERMAN)


def test_the_persona_is_told_it_answered_the_phone(prompt):
    assert "you are the one who answered the phone" in prompt
    assert "the user called you" in prompt


def test_the_persona_is_not_told_it_called(prompt):
    assert "you are the one who called" not in prompt
    assert "never wait for them to explain why they're calling" not in prompt


def test_the_persona_may_not_give_a_reason_for_calling(prompt):
    assert "never give a reason for calling" in prompt


def test_the_persona_is_the_one_who_can_act(prompt):
    assert "You are the one who can do something about it" in prompt
    assert "ideas, offers and remedies" not in prompt


def test_an_ordinary_scenario_keeps_the_ordinary_casting(persona, played):
    ordinary = build_system_prompt(persona, played, GERMAN)
    assert "you are the one who called" in ordinary
    assert "answered the phone" not in ordinary


def test_the_personas_role_is_dropped(prompt, persona):
    assert persona.role not in prompt


def test_the_personas_objections_are_dropped(prompt, persona):
    for objection in persona.objections:
        assert objection not in prompt


def test_the_personas_character_is_kept(prompt, persona):
    assert persona.name in prompt
    assert persona.traits in prompt
    assert persona.behavior in prompt


def test_the_case_is_the_same_three_fields(prompt):
    for value in _CASE.values():
        assert value in prompt


def test_the_goal_is_named_as_the_callers_and_not_the_personas(prompt):
    assert "What the caller wants from this call" in prompt
    assert "That is their goal and not yours" in prompt
    assert "What you want from this call" not in prompt


def test_the_settlement_bar_is_the_callers(prompt):
    assert "when they will count the matter settled" in prompt
    assert "That is their bar" in prompt
    assert "when you count the matter settled" not in prompt


def test_the_facts_are_the_personas_records(prompt):
    assert "as they stand on your side" in prompt
    assert "This is what your records show" in prompt


def test_a_scenario_without_a_case_produces_no_dangling_headings(persona, played):
    empty = replace(played, reverse=True, case_facts="", call_goal="")
    prompt = build_system_prompt(persona, empty, GERMAN)
    assert "Facts of the case" not in prompt
    assert "What the caller wants from this call" not in prompt
    assert "settled when" not in prompt


def test_the_call_ends_when_the_caller_has_what_they_came_for(prompt):
    assert "whether the caller now has what they came for" in prompt
    assert "[CALL_END]" in prompt


def test_the_persona_does_not_hang_up_on_a_caller(prompt):
    assert "You do not hang up on a caller" in prompt
    assert "Never end the call while your concern is still unresolved" not in prompt


def test_the_opening_asks_only_for_a_line_answering_the_phone():
    instruction = opening_instruction(GERMAN, reverse=True)
    assert "picking it up" in instruction
    assert GERMAN.answering_examples in instruction


def test_the_opening_forbids_guessing_at_the_case():
    instruction = opening_instruction(GERMAN, reverse=True)
    assert "You do not know who is calling or what about" in instruction
    assert "do not guess at their reason" in instruction


def test_the_ordinary_opening_is_unchanged():
    ordinary = opening_instruction(GERMAN)

    assert GERMAN.opening_examples in ordinary
    assert GERMAN.answering_examples not in ordinary
    assert ordinary == opening_instruction(GERMAN, reverse=False)


def test_every_language_pack_can_answer_a_phone():
    for code in ("de", "en"):
        assert get_pack(code).answering_examples.strip()


def test_the_notes_are_kept_by_the_side_that_answered(persona, reversed_scenario):
    messages = build_state_prompt("", "Guten Tag.", "Beck hier.", persona, reversed_scenario)
    system = messages[0]["content"]
    assert "the person who answered a phone call" in system
    assert "the user is the customer who rang them" in system
    assert "has called the user" not in system


def test_the_notes_label_the_exchange_like_the_transcript(persona, reversed_scenario):
    messages = build_state_prompt("", "Guten Tag.", "Beck hier.", persona, reversed_scenario)
    assert "Agent: Beck hier." in messages[1]["content"]


def test_the_ordinary_notes_are_unchanged(persona, played):
    messages = build_state_prompt("", "Guten Tag.", "Brandt hier.", persona, played)
    assert "The caller is playing" in messages[0]["content"]
    assert "Caller: Brandt hier." in messages[1]["content"]


def test_the_settlement_check_asks_whether_the_caller_was_given_it(reversed_scenario):
    assert "Have you actually given the caller that" in SETTLEMENT_CHECK_REVERSE
    assert "Has the user actually given you that" not in SETTLEMENT_CHECK_REVERSE
    # And the criterion it is formatted with is still the Scenario's own.
    filled = SETTLEMENT_CHECK_REVERSE.format(criterion=reversed_scenario.call_goal)
    assert reversed_scenario.call_goal in filled


def test_the_anti_repeat_nudge_lets_a_reverse_persona_offer_something():
    assert "as though it were your own idea" in ANTI_REPEAT_NUDGE
    assert "as though it were your own idea" not in ANTI_REPEAT_NUDGE_REVERSE
    assert "put forward what you can actually do" in ANTI_REPEAT_NUDGE_REVERSE


def test_the_reversed_nudge_still_demands_something_new():
    assert "Do not repeat or reword that reply" in ANTI_REPEAT_NUDGE_REVERSE
    assert "do not greet or introduce yourself again" in ANTI_REPEAT_NUDGE_REVERSE
    filled = ANTI_REPEAT_NUDGE_REVERSE.format(previous="Da kann ich nichts machen.")
    assert "Da kann ich nichts machen." in filled


def test_the_ordinary_nudge_still_speaks_from_the_callers_side():
    assert "ask a new question about your own concern" in ANTI_REPEAT_NUDGE
    assert "caller" not in ANTI_REPEAT_NUDGE


# Per-turn assembly must pick the reversed forms by the Scenario's flag.


def _standing_nudge(orch, replies=3):
    # pylint: disable=protected-access  # the assembly is the unit under test
    for i in range(replies):
        orch.history.add_reply(f"Antwort {i}.")
    return orch._messages_for_turn(closing=False)[-1]["content"]


def test_a_reverse_turn_carries_the_reversed_nudge_and_check(persona, reversed_scenario):
    nudge = _standing_nudge(SessionOrchestrator(persona, reversed_scenario))

    assert "put forward what you can actually do" in nudge
    assert "Have you actually given the caller that" in nudge
    assert reversed_scenario.call_goal in nudge


def test_an_ordinary_turn_carries_neither(persona, played):
    nudge = _standing_nudge(SessionOrchestrator(persona, played))

    assert "put forward what you can actually do" not in nudge
    assert "Have you actually given the caller that" not in nudge
    assert "Has the user actually given you that" in nudge
