"""Closing-intent detection.

Covers ADR 0037: a deterministic regex (no LLM classifier) recognises two
categories of user signal that the call is over — an explicit farewell, or a
request to postpone / continue elsewhere — and nudges the persona to end.

ADR 0043: the patterns match the *user's* transcribed speech, which is in the
Persona's language, so they live in the language pack rather than in the
English prompt frame. Both packs are exercised here.
"""

import pytest

from backend.session.language_packs import get_pack
from backend.session.models import TurnCompleted
from backend.session.orchestrator import SessionOrchestrator, _asks_to_repeat, _signals_closing
from tests.conftest import collect, completed, states

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
    """ADR 0043: an English-speaking Persona needs its own patterns — the
    German ones would never match what its user actually says."""
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
    """language_packs.py states the trade: a missed signal costs one extra turn,
    a false one cuts the conversation off. These all contain a closing phrase
    while saying the opposite of goodbye, and each one used to end the call."""
    assert _signals_closing(text, GERMAN) is False


@pytest.mark.parametrize(
    "text",
    [
        "Ich kann nicht länger warten, auf Wiederhören.",
        "Ich habe gerade keine Zeit, machen wir das ein anderes Mal.",
    ],
)
def test_a_negation_in_an_earlier_clause_still_leaves_a_real_goodbye_standing(text):
    """The veto is scoped to the closing phrase's own clause. A negation on the
    other side of a comma belongs to a different statement and must not
    suppress a genuine farewell."""
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
    """A false repeat request costs a whole turn: the persona re-delivers its
    last line instead of answering the objection (ADR 0038)."""
    assert _asks_to_repeat(text, GERMAN) is False


@pytest.mark.parametrize(
    "text",
    ["Das habe ich nicht verstanden.", "Wie bitte?", "Können Sie das nochmal sagen?"],
)
def test_genuine_repeat_requests_still_register(text):
    assert _asks_to_repeat(text, GERMAN) is True


def test_each_language_uses_its_own_patterns():
    """ADR 0043: a pack is not a translation of the frame, it is what makes the
    check work at all — the wrong pack simply does not match."""
    assert _signals_closing("Auf Wiederhören.", ENGLISH) is False
    assert _signals_closing("Goodbye.", GERMAN) is False


async def test_farewell_makes_the_persona_end_the_call(persona, scenario, fake_pipeline):
    """ADR 0037/0038: on a detected farewell the persona is nudged to close,
    the turn is marked ends_call, and no 'listening' follows."""
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
