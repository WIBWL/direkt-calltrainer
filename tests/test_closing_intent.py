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
from backend.session.orchestrator import SessionOrchestrator, _signals_closing
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
