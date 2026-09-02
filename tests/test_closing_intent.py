"""Closing-intent detection.

Covers ADR 0037: a deterministic regex (no LLM classifier) recognises two
categories of user signal that the call is over — an explicit farewell, or a
request to postpone / continue elsewhere — and nudges the persona to end.
"""

import pytest

from backend.session.models import TurnCompleted
from backend.session.orchestrator import SessionOrchestrator, _signals_closing
from tests.conftest import collect, completed, states

# pylint: disable=missing-function-docstring


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
    assert _signals_closing(text) is True


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
    assert _signals_closing(text) is False


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
