"""Barge-in / eager interruption of an in-flight turn.

Covers ADR 0035:
  * tearing down the turn generator mid-flight finalizes the turn at once
  * if no audio was played yet, the SAME turn stays open and the next
    utterance is appended onto the pending question ("wait, also -")
  * only words actually dispatched as audio are committed to history;
    generated-but-unsent text is discarded
"""

import asyncio

import pytest

from backend.session.models import AudioChunk, StateChanged
from backend.session.orchestrator import SessionOrchestrator
from tests.conftest import collect

# pylint: disable=missing-function-docstring,protected-access


async def _drain_until(gen, predicate):
    """Consume events until predicate(event) is true; return collected events."""
    seen = []
    async for event in gen:
        seen.append(event)
        if predicate(event):
            return seen
    return seen


async def test_interrupt_before_any_audio_reopens_the_same_turn(persona, scenario, fake_pipeline):
    """No audio was sent yet -> the turn stays open and the follow-up
    utterance is merged onto the same question."""
    fake_pipeline.tts.hang = asyncio.Event()  # park synthesis so no audio is ever produced

    fake_pipeline.stt.transcripts = ["Erste Haelfte der Frage.", "Und jetzt der Rest davon."]
    fake_pipeline.llm.replies = ["Antwort die nie gehoert wird.", "Die richtige, vollstaendige Antwort."]

    orch = SessionOrchestrator(persona, scenario)
    gen = orch.run_turn(b"a", "turn.webm", "audio/webm")

    # Consume 'thinking', then let the pipeline run until it parks on the
    # hanging synth, then barge in.
    await _drain_until(gen, lambda e: isinstance(e, StateChanged) and e.state == "thinking")
    with pytest.raises((asyncio.TimeoutError, TimeoutError)):
        await asyncio.wait_for(gen.__anext__(), timeout=0.3)
    await gen.aclose()

    assert len(orch.turns) == 1
    assert orch.turns[0].persona_text == "", "unsent generated text is discarded"
    assert orch.turns[0].user_text == "Erste Haelfte der Frage."

    # Continuation turn with a working synth.
    fake_pipeline.tts.hang = None
    events = await collect(orch.run_turn(b"b", "turn.webm", "audio/webm"))

    assert len(orch.turns) == 1, "the continuation reuses the same turn"
    assert orch.turns[0].user_text == "Erste Haelfte der Frage. Und jetzt der Rest davon."
    assert any(isinstance(e, AudioChunk) for e in events)


async def test_interrupt_after_partial_audio_commits_only_spoken_words(persona, scenario, fake_pipeline):
    s1 = (
        "Der erste Teil meiner Antwort ist hier inhaltlich vollstaendig "
        "und auf jeden Fall lang genug, um sauber abgetrennt zu werden."
    )
    s2 = "Diesen zweiten Teil hoert der Nutzer nicht mehr, weil er dazwischenredet."
    assert len(s1) >= 80
    fake_pipeline.stt.transcripts = ["Erklaeren Sie mir das bitte."]
    fake_pipeline.llm.replies = [s1 + " " + s2]

    orch = SessionOrchestrator(persona, scenario)
    gen = orch.run_turn(b"a", "turn.webm", "audio/webm")
    await _drain_until(gen, lambda e: isinstance(e, AudioChunk))
    await gen.aclose()  # barge in right after the first chunk was sent

    assert orch.turns[0].persona_text == s1
    assert s2 not in orch.turns[0].persona_text
    assert orch._reopen_turn is None, "a turn that already produced audio is closed, not reopened"


async def test_new_or_reopened_turn_bookkeeping(persona, scenario):
    orch = SessionOrchestrator(persona, scenario)
    t1, reopening1 = orch._new_or_reopened_turn()
    assert reopening1 is False and t1.seq == 1 and orch.turns == [t1]

    t2, reopening2 = orch._new_or_reopened_turn()
    assert reopening2 is True and t2 is t1, "still-open turn is reused"
    assert orch.turns == [t1], "no second turn was appended"
