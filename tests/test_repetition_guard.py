"""Degenerate-repetition guard and guaranteed closing line.

Covers ADR 0038:
  * a reply that repeats the persona's previous message, or repeats a
    sentence within itself, is treated as "the model has nothing left to
    say" and ends the call
  * on a backstopped ending (repetition, or an unprompted [CALL_END] that
    was never nudged) a fixed German sign-off is synthesised and appended
"""

import pytest

from backend.session.orchestrator import (
    _FALLBACK_CLOSING_LINE,
    SessionOrchestrator,
    _has_repeated_sentence,
)
from tests.conftest import audio_chunks, collect, completed, states

# pylint: disable=missing-function-docstring


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Das ist ein vollstaendiger Satz. Das ist ein vollstaendiger Satz.", True),
        ("Erste Aussage hier zum Thema. Eine voellig andere zweite Aussage.", False),
        ("Ja. Ja. Ja.", False),  # too short to count
        ("Nur ein einziger, ausreichend langer Satz ohne jede Wiederholung.", False),
    ],
)
def test_has_repeated_sentence(text, expected):
    assert _has_repeated_sentence(text) is expected


async def test_reply_repeating_the_previous_reply_ends_the_call(persona, scenario, fake_pipeline):
    line = "Ich brauche dazu bitte eine konkrete Zahl von Ihnen."
    fake_pipeline.stt.transcripts = ["Ich schaue mal nach.", "Einen Moment noch."]
    fake_pipeline.llm.replies = [line, line]  # second turn repeats the first verbatim

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))
    events = await collect(orch.run_turn(b"b", "turn.webm", "audio/webm"))

    tc = completed(events)
    assert tc is not None and tc.ends_call is True
    assert "listening" not in states(events)


async def test_backstopped_ending_appends_the_fixed_closing_line(persona, scenario, fake_pipeline):
    """An unprompted [CALL_END] (no farewell from the user) is not trusted to
    contain a goodbye, so the fixed sign-off is synthesised and appended."""
    fake_pipeline.stt.transcripts = ["Gut, dann machen wir das so."]
    fake_pipeline.llm.replies = ["In Ordnung. [CALL_END]"]

    orch = SessionOrchestrator(persona, scenario)
    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    assert completed(events).ends_call is True
    assert _FALLBACK_CLOSING_LINE in orch.turns[-1].persona_text
    # the fixed line was actually synthesised, not just appended to text
    assert any(_FALLBACK_CLOSING_LINE.encode("utf-8") in c.audio for c in audio_chunks(events))


async def test_nudged_ending_trusts_the_models_own_goodbye(persona, scenario, fake_pipeline):
    """When the user said goodbye, the model was explicitly asked for a
    closing line, so the fixed fallback is NOT appended on top."""
    fake_pipeline.stt.transcripts = ["Auf Wiederhören!"]
    fake_pipeline.llm.replies = ["Danke fuer das Gespraech, auf Wiederhoeren. [CALL_END]"]

    orch = SessionOrchestrator(persona, scenario)
    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    assert completed(events).ends_call is True
    assert _FALLBACK_CLOSING_LINE not in orch.turns[-1].persona_text
