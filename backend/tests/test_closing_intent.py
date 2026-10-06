"""Closing-intent regexes in both language packs (ADR 0037, 0043)."""

from dataclasses import replace

import pytest

from shared.language_packs import get_pack
from backend.session.events import TurnCompleted
from backend.session.nudges import SETTLEMENT_CHECK_AFTER_REPLIES
from backend.session.orchestrator import (
    SessionOrchestrator,
    _asks_to_repeat,
    _signals_closing,
)
from backend.tests.conftest import collect, completed, states

# _signals_closing is the unit under test here.
# pylint: disable=missing-function-docstring,protected-access

GERMAN = get_pack("de")
ENGLISH = get_pack("en")


@pytest.mark.parametrize(
    "text",
    [
        "Okay, tschüss dann!",
        "Alles klar, auf Wiederhören.",
        "Auf Wiedersehen und danke.",
        "Na dann ciao.",
        "Können wir das ein anderes Mal fortsetzen?",
        "Ich melde mich später nochmal bei Ihnen.",
        "Ich rufe Sie später zurück.",
        "Ich habe gerade keine Zeit mehr dafür.",
        "Ich muss jetzt auflegen.",
        "Lassen Sie uns das Gespräch beenden.",
        # Said to the persona live and missed: the inflected verb before the noun.
        "Ja, ich beende das Gespräch jetzt hier.",
        "Ich beende das Telefonat.",
        "Ich lege jetzt auf.",
    ],
)
def test_recognises_farewells_and_postponements(text):
    assert _signals_closing(text, GERMAN) is True


@pytest.mark.parametrize(
    "text",
    [
        "Können Sie mir die Vertragslaufzeit noch nennen?",
        "Das verstehe ich nicht ganz, erklären Sie das nochmal.",
        "Warum kostet das denn so viel?",
        "Ich bin mit dem Preis nicht zufrieden.",
        # The veto reads only the clause before a match, so the trailing
        # negation is guarded in the pattern itself.
        "Ich beende das Gespräch nicht, ich habe noch eine Frage.",
        "Ich lege Wert auf eine schnelle Lösung.",
    ],
)
def test_does_not_fire_on_ordinary_conversation(text):
    assert _signals_closing(text, GERMAN) is False


@pytest.mark.parametrize(
    "text",
    [
        "Okay, goodbye then!",
        "Right, take care.",
        "Thanks, have a good day.",
        "Could we pick this up another time?",
        "I'll call you back later.",
        "I have no time right now.",
        "I need to go, sorry.",
        "Let's end this call here.",
    ],
)
def test_recognises_english_farewells_and_postponements(text):
    assert _signals_closing(text, ENGLISH) is True


@pytest.mark.parametrize(
    "text",
    [
        "Could you tell me the contract term as well?",
        "I do not quite follow, could you explain that again?",
        "Why does that cost so much?",
    ],
)
def test_english_patterns_do_not_fire_on_ordinary_conversation(text):
    assert _signals_closing(text, ENGLISH) is False


@pytest.mark.parametrize(
    "text",
    [
        # The phrase is the object of the sentence, not its act.
        "Bevor wir auf Wiederhören sagen, hätte ich noch eine Frage.",
        "Sagen Sie nicht einfach tschüss und legen auf, das akzeptiere ich nicht.",
        # "no time *for* X" is a complaint about X. Complaint Scenarios are
        # seeded, so this is where it turns up.
        "Ich habe keine Zeit mehr für diese ständigen Verzögerungen!",
        "Ich will das Gespräch gar nicht beenden, ich will eine Lösung.",
    ],
)
def test_a_farewell_that_is_only_mentioned_does_not_end_the_call(text):
    assert _signals_closing(text, GERMAN) is False


@pytest.mark.parametrize(
    "text",
    [
        "Ich kann nicht länger warten, auf Wiederhören.",
        "Ich habe gerade keine Zeit, machen wir das ein anderes Mal.",
    ],
)
def test_a_negation_in_an_earlier_clause_still_leaves_a_real_goodbye_standing(text):
    assert _signals_closing(text, GERMAN) is True


@pytest.mark.parametrize(
    "text",
    [
        "I won't be able to sort this out today, goodbye.",
        "I have no time right now.",
    ],
)
def test_english_closings_survive_the_veto(text):
    assert _signals_closing(text, ENGLISH) is True


def test_english_mentioned_farewell_does_not_end_the_call():
    assert _signals_closing("Do not just say goodbye and hang up on me.", ENGLISH) is False


@pytest.mark.parametrize(
    "text",
    [
        # An objection to the substance, not a request to hear it again.
        "Ich kann nicht verstehen, warum Sie mir das nicht erstatten!",
        "Ich habe nicht verstanden, wieso das so lange dauert.",
    ],
)
def test_an_objection_is_not_a_request_to_repeat(text):
    assert _asks_to_repeat(text, GERMAN) is False


@pytest.mark.parametrize(
    "text",
    ["Das habe ich nicht verstanden.", "Wie bitte?", "Können Sie das nochmal sagen?"],
)
def test_genuine_repeat_requests_still_register(text):
    assert _asks_to_repeat(text, GERMAN) is True


def test_each_language_uses_its_own_patterns():
    assert _signals_closing("Auf Wiederhören.", ENGLISH) is False
    assert _signals_closing("Goodbye.", GERMAN) is False


async def test_farewell_makes_the_persona_end_the_call(persona, scenario, fake_pipeline):
    orch = SessionOrchestrator(persona, scenario)
    fake_pipeline.stt.transcripts = ["Das reicht mir so weit, auf Wiederhören."]
    fake_pipeline.llm.replies = ["Sehr gern, ich wünsche Ihnen noch einen guten Tag. [CALL_END]"]

    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    tc = completed(events)
    assert isinstance(tc, TurnCompleted) and tc.ends_call is True
    assert "listening" not in states(events)


async def test_closing_nudge_is_added_to_the_llm_messages(persona, scenario, fake_pipeline):
    orch = SessionOrchestrator(persona, scenario)
    fake_pipeline.stt.transcripts = ["Tschüss!"]
    fake_pipeline.llm.replies = ["Auf Wiederhören. [CALL_END]"]

    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    sent_messages = fake_pipeline.llm.calls[-1]
    assert any(
        m["role"] == "system" and "call is over" in m["content"].lower()
        for m in sent_messages
    )


def _standing_nudge(orch, replies=3):
    for i in range(replies):
        orch.history.add_reply(f"Antwort {i}.")
    return orch._messages_for_turn(closing=False)[-1]["content"]


def test_standing_nudge_restates_the_settlement_bar(persona, scenario):
    with_condition = replace(scenario, call_goal="a refund date is named")
    nudge = _standing_nudge(SessionOrchestrator(persona, with_condition))

    assert "a refund date is named" in nudge
    assert "close the call the way your instructions describe" in nudge


def test_standing_nudge_does_not_spell_out_the_marker(persona, scenario):
    nudge = _standing_nudge(SessionOrchestrator(persona, scenario))

    assert "[CALL_END]" not in nudge


def test_standing_nudge_puts_the_open_case_first(persona, scenario):
    nudge = _standing_nudge(SessionOrchestrator(persona, scenario))

    assert "press a point you have not pressed yet" in nudge
    assert "carry the call on" in nudge
    assert nudge.index("press a point you have not pressed yet") < nudge.index("carry the call on")


def test_settlement_check_falls_back_without_a_call_goal(persona, scenario):
    nudge = _standing_nudge(SessionOrchestrator(persona, scenario))

    assert "what you came for has been given" in nudge


def test_settlement_check_is_withheld_over_the_opening_exchanges(persona, scenario):
    early = _standing_nudge(
        SessionOrchestrator(persona, replace(scenario, call_goal="a date is named")),
        replies=SETTLEMENT_CHECK_AFTER_REPLIES - 1,
    )

    assert "a date is named" not in early
    # The anti-repeat nudge is untouched by the gate.
    assert "Say something genuinely different now" in early


def test_closing_turn_carries_only_the_closing_nudge(persona, scenario):
    orch = SessionOrchestrator(persona, replace(scenario, call_goal="a date is named"))
    orch.history.add_reply("Vorherige Antwort.")

    nudge = orch._messages_for_turn(closing=True)[-1]["content"]

    assert "call is over" in nudge.lower()
    assert "a date is named" not in nudge
