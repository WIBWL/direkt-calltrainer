"""The swapped casting a reverse runs under (F-61, ADR 0070).

A reverse replays one finished Session with the roles turned around: the User
rings and the Persona picks up. Everything the pipeline does stays the same, so
what is asserted here is only what the model is *told* — and, just as much,
that an ordinary Scenario is told none of it.

Covers:
  F-61      the User calls, the Persona answers
  ADR 0070  the casting is swapped in the one prompt, not in a second one;
            role and objections are dropped; the opening is a greeting only
  ADR 0043  instructions stay English, the spoken language comes from the pack
  ADR 0045  the case keeps its three fields; they are relabelled, not rewritten
  ADR 0071  the call-state notes are kept from the same side as the prompt
  ADR 0073  the settlement check asks about the caller's bar either way
  ADR 0038  the per-turn anti-repeat nudge turns around with the casting

No database, no network: these are pure functions over a Persona and a
Scenario, plus one assembled by an orchestrator that never connects to
anything. `tests/test_system_prompt.py` is the guard on the ordinary prompt and
keeps holding — the tests below only add that the reverse text never leaks into
it.
"""

from dataclasses import replace

import pytest

from backend.session.language_packs import get_pack
from backend.session.nudges import (
    ANTI_REPEAT_NUDGE, ANTI_REPEAT_NUDGE_REVERSE, SETTLEMENT_CHECK_REVERSE,
)
from backend.session.orchestrator import SessionOrchestrator
from backend.session.prompting import (
    build_state_prompt, build_system_prompt, opening_instruction,
)
from tests.conftest import TEST_PERSONAS, TEST_SCENARIOS

# The builders are the unit under test.
# pylint: disable=missing-function-docstring,redefined-outer-name

GERMAN = get_pack("de")

# A case on both, so the reverse block has all three fields to turn around.
_CASE = {
    "case_facts": "A ticket was opened eleven days ago; a callback was promised.",
    "call_goal": "Find out what is happening and get a date.",
    "success_condition": "someone names a date. A promise to look into it is not enough.",
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


# --- The casting ----------------------------------------------------------


def test_the_persona_is_told_it_answered_the_phone(prompt):
    """F-61: the whole exercise rests on this one fact being the right way
    round."""
    assert "you are the one who answered the phone" in prompt
    assert "the user called you" in prompt


def test_the_persona_is_not_told_it_called(prompt):
    """The ordinary casting must be gone, not merely contradicted later: a 4B
    model handed both reads whichever it saw last (ADR 0011)."""
    assert "you are the one who called" not in prompt
    assert "never wait for them to explain why they're calling" not in prompt


def test_the_persona_may_not_give_a_reason_for_calling(prompt):
    assert "never give a reason for calling" in prompt


def test_the_persona_is_the_one_who_can_act(prompt):
    """The other half of the casting: solutions come from the Persona now,
    which is exactly the sentence the ordinary prompt reverses."""
    assert "You are the one who can do something about it" in prompt
    assert "ideas, offers and remedies" not in prompt


def test_an_ordinary_scenario_keeps_the_ordinary_casting(persona, played):
    """The guard: nothing above may reach a Scenario that is not a reverse."""
    ordinary = build_system_prompt(persona, played, GERMAN)
    assert "you are the one who called" in ordinary
    assert "answered the phone" not in ordinary


# --- The Persona's own fields ---------------------------------------------


def test_the_personas_role_is_dropped(prompt, persona):
    """ADR 0070: every seeded role describes a customer, so handing it to a
    Persona now working the support line casts it as both sides at once."""
    assert persona.role not in prompt


def test_the_personas_objections_are_dropped(prompt, persona):
    """Same reason: they are a customer's objections."""
    for objection in persona.objections:
        assert objection not in prompt


def test_the_personas_character_is_kept(prompt, persona):
    """An impatient agent is a fair counterpart — the character is not what
    the swap is about."""
    assert persona.name in prompt
    assert persona.traits in prompt
    assert persona.behavior in prompt


# --- The case -------------------------------------------------------------


def test_the_case_is_the_same_three_fields(prompt):
    """ADR 0045's fields carry over verbatim; only their labels turn around."""
    for value in _CASE.values():
        assert value in prompt


def test_the_goal_is_named_as_the_callers_and_not_the_personas(prompt):
    """The failure this prevents: handed "What you want from this call" while
    playing the callee, the model made the User's demands at the User."""
    assert "What the caller wants from this call" in prompt
    assert "That is their goal and not yours" in prompt
    assert "What you want from this call" not in prompt


def test_the_settlement_condition_is_the_callers_bar(prompt):
    assert "The caller will count the matter as settled when" in prompt
    assert "That is their bar" in prompt
    assert "You consider the matter settled when" not in prompt


def test_the_facts_are_the_personas_records(prompt):
    """The ownership line turns around with the casting: what the caller must
    not be asked about becomes what is on file with you."""
    assert "as they stand on your side" in prompt
    assert "This is what your records show" in prompt


def test_a_scenario_without_a_case_produces_no_dangling_headings(persona, played):
    """Each field is optional on its own, exactly as in the ordinary block."""
    empty = replace(played, reverse=True, case_facts="", call_goal="", success_condition="")
    prompt = build_system_prompt(persona, empty, GERMAN)
    assert "Facts of the case" not in prompt
    assert "What the caller wants from this call" not in prompt
    assert "settled when" not in prompt


# --- Closing --------------------------------------------------------------


def test_the_call_ends_when_the_caller_has_what_they_came_for(prompt):
    assert "whether the caller now has what they came for" in prompt
    assert "[CALL_END]" in prompt


def test_the_persona_does_not_hang_up_on_a_caller(prompt):
    """The ordinary rule is about the Persona's own unmet concern, which it no
    longer has; what replaces it is the plain fact about answering a phone."""
    assert "You do not hang up on a caller" in prompt
    assert "Never end the call while your concern is still unresolved" not in prompt


# --- The opening ----------------------------------------------------------


def test_the_opening_asks_only_for_a_line_answering_the_phone():
    """F-61: the Persona still speaks first, it just says less."""
    instruction = opening_instruction(GERMAN, reverse=True)
    assert "picking it up" in instruction
    assert GERMAN.answering_examples in instruction


def test_the_opening_forbids_guessing_at_the_case():
    """A callee that names the reason has answered the exercise before it
    started."""
    instruction = opening_instruction(GERMAN, reverse=True)
    assert "You do not know who is calling or what about" in instruction
    assert "do not guess at their reason" in instruction


def test_the_ordinary_opening_is_unchanged():
    """Same guard as on the casting: the default argument must keep meaning
    what it meant."""
    assert opening_instruction(GERMAN) == opening_instruction(GERMAN, reverse=False)
    assert GERMAN.opening_examples in opening_instruction(GERMAN)


def test_every_language_pack_can_answer_a_phone():
    """A pack without the examples would fall back to nothing at all, so a
    further language has to bring them (ADR 0043)."""
    for code in ("de", "en"):
        assert get_pack(code).answering_examples.strip()


# --- The call-state notes (ADR 0071) --------------------------------------


def test_the_notes_are_kept_by_the_side_that_answered(persona, reversed_scenario):
    """These notes are most of what the model still sees of the call, so a
    frame naming the wrong side undoes the system prompt one exchange at a
    time."""
    messages = build_state_prompt("", "Guten Tag.", "Beck hier.", persona, reversed_scenario)
    system = messages[0]["content"]
    assert "the person who answered a phone call" in system
    assert "the user is the customer who rang them" in system
    assert "has called the user" not in system


def test_the_notes_label_the_exchange_like_the_transcript(persona, reversed_scenario):
    """`Agent`, the same word the wrap-up's dossier uses (ADR 0070), so the
    machine is never called "Caller" while the trainee was the caller."""
    messages = build_state_prompt("", "Guten Tag.", "Beck hier.", persona, reversed_scenario)
    assert "Agent: Beck hier." in messages[1]["content"]


def test_the_ordinary_notes_are_unchanged(persona, played):
    messages = build_state_prompt("", "Guten Tag.", "Brandt hier.", persona, played)
    assert "The caller is playing" in messages[0]["content"]
    assert "Caller: Brandt hier." in messages[1]["content"]


# --- The settlement check (ADR 0073) --------------------------------------


def test_the_settlement_check_asks_whether_the_caller_was_given_it(reversed_scenario):
    """The direction is the whole difference: asked the ordinary question while
    playing the support side, the model started pressing the caller for the
    thing the caller had rung about."""
    assert "Have you actually given the caller that" in SETTLEMENT_CHECK_REVERSE
    assert "Has the user actually given you that" not in SETTLEMENT_CHECK_REVERSE
    # And the criterion it is formatted with is still the Scenario's own.
    filled = SETTLEMENT_CHECK_REVERSE.format(criterion=reversed_scenario.success_condition)
    assert reversed_scenario.success_condition in filled


# --- The per-turn anti-repeat nudge (ADR 0038) -----------------------------


def test_the_anti_repeat_nudge_lets_a_reverse_persona_offer_something():
    """The ordinary nudge forbids putting the user's proposal forward as the
    persona's own -- which reversed is the persona's actual job, stated from
    the position in context that measurably decides the reply. Left as it was,
    the nudge nearest the answer contradicted the casting the system prompt
    had set three hundred lines earlier."""
    assert "as though it were your own idea" in ANTI_REPEAT_NUDGE
    assert "as though it were your own idea" not in ANTI_REPEAT_NUDGE_REVERSE
    assert "put forward what you can actually do" in ANTI_REPEAT_NUDGE_REVERSE


def test_the_reversed_nudge_still_demands_something_new():
    """What the nudge is *for* is unchanged -- only who solves the call moved
    (ADR 0038)."""
    assert "Do not repeat or reword that reply" in ANTI_REPEAT_NUDGE_REVERSE
    assert "do not greet or introduce yourself again" in ANTI_REPEAT_NUDGE_REVERSE
    filled = ANTI_REPEAT_NUDGE_REVERSE.format(previous="Da kann ich nichts machen.")
    assert "Da kann ich nichts machen." in filled


def test_the_ordinary_nudge_still_speaks_from_the_callers_side():
    """The guard: the reversed wording must not have leaked into the one every
    ordinary call carries."""
    assert "ask a new question about your own concern" in ANTI_REPEAT_NUDGE
    assert "caller" not in ANTI_REPEAT_NUDGE


# --- What the orchestrator actually attaches -------------------------------
#
# The two constants above are worth nothing unless the per-turn message
# assembly reaches for them, and which one it reaches for is decided by a flag
# on the Scenario. Asserted through `_messages_for_turn` rather than by reading
# the branch, because that is the thing a later refactor can quietly break.


def _standing_nudge(orch, replies=3):
    """The transient system message a turn past the opening carries. `replies`
    is how far into the call it is -- the settlement check is withheld over the
    opening exchanges (ADR 0073)."""
    # pylint: disable=protected-access  # the assembly is the unit under test
    for i in range(replies):
        orch._messages.append({"role": "assistant", "content": f"Antwort {i}."})
    return orch._messages_for_turn(closing=False)[-1]["content"]


def test_a_reverse_turn_carries_the_reversed_nudge_and_check(persona, reversed_scenario):
    nudge = _standing_nudge(SessionOrchestrator(persona, reversed_scenario))

    assert "put forward what you can actually do" in nudge
    assert "Have you actually given the caller that" in nudge
    assert reversed_scenario.success_condition in nudge


def test_an_ordinary_turn_carries_neither(persona, played):
    """The guard, again: a reverse must not change what every other call is
    told."""
    nudge = _standing_nudge(SessionOrchestrator(persona, played))

    assert "put forward what you can actually do" not in nudge
    assert "Have you actually given the caller that" not in nudge
    assert "Has the user actually given you that" in nudge
