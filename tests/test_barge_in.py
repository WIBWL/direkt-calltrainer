"""Barge-in / eager interruption of an in-flight turn.

Covers ADR 0035:
  * tearing down the turn generator mid-flight finalizes the turn at once
  * if no audio was played yet, the SAME turn stays open and the next
    utterance is appended onto the pending question ("wait, also -")
  * only the utterances whose audio the client reports it played through are
    committed to history; anything streamed ahead but unheard is discarded
  * a client that sends no playback position falls back to committing every
    dispatched chunk (the pre-ADR-0035-revision behaviour)
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


async def test_interrupt_without_a_reported_position_commits_every_dispatched_chunk(
    persona, scenario, fake_pipeline
):
    """No played_ms (an older client) -> the server can't tell what was heard,
    so it falls back to committing everything it dispatched as audio."""
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


async def test_interrupt_commits_only_utterances_played_through(persona, scenario, fake_pipeline, monkeypatch):
    """The client reports how many ms of the reply it actually played; only the
    utterances whose audio finished inside that window reach the history, even
    though the server had already streamed the whole reply ahead."""
    monkeypatch.setattr("backend.session.orchestrator.tts.duration_ms", lambda _wav: 1000)
    # Each >= 80 chars so the chunker flushes all three as their own chunks.
    s1 = "Der erste Satz meiner Antwort ist inhaltlich vollstaendig und lang genug fuer seinen eigenen Chunk."
    s2 = "Der zweite Satz folgt unmittelbar darauf und ist ebenfalls lang genug fuer einen eigenen Chunk hier."
    s3 = "Den dritten und letzten Satz hoert der Nutzer schon gar nicht mehr, weil er laengst dazwischenredet."
    assert min(len(s1), len(s2), len(s3)) >= 80
    fake_pipeline.stt.transcripts = ["Bitte erklaeren Sie mir das."]
    fake_pipeline.llm.replies = [f"{s1} {s2} {s3}"]

    orch = SessionOrchestrator(persona, scenario)
    gen = orch.run_turn(b"a", "turn.webm", "audio/webm")

    dispatched = 0
    async for event in gen:
        if isinstance(event, AudioChunk):
            dispatched += 1
            if dispatched == 3:  # the server has streamed all three chunks
                break

    orch.note_barge_in(1200)  # the client only played ~1.2s -> one full utterance
    await gen.aclose()

    assert orch.turns[0].persona_text == s1
    assert s2 not in orch.turns[0].persona_text
    assert s3 not in orch.turns[0].persona_text
    assert orch._messages[-1] == {"role": "assistant", "content": s1}
    assert orch._reopen_turn is None


async def test_interrupt_before_a_full_utterance_was_heard_reopens_the_turn(
    persona, scenario, fake_pipeline, monkeypatch
):
    """Audio started but the client played less than one full utterance -> treat
    it like the no-audio case: discard the reply, keep the turn open."""
    monkeypatch.setattr("backend.session.orchestrator.tts.duration_ms", lambda _wav: 1000)
    fake_pipeline.stt.transcripts = ["Erste Haelfte.", "Und der Rest."]
    fake_pipeline.llm.replies = ["Ein ganzer Satz den der Nutzer fast sofort abschneidet.", "Die echte Antwort."]

    orch = SessionOrchestrator(persona, scenario)
    gen = orch.run_turn(b"a", "turn.webm", "audio/webm")
    await _drain_until(gen, lambda e: isinstance(e, AudioChunk))
    orch.note_barge_in(120)  # a fraction of a second -> nothing heard in full
    await gen.aclose()

    assert orch.turns[0].persona_text == ""
    assert orch._reopen_turn is orch.turns[0], "nothing was heard, so the turn stays open"

    events = await collect(orch.run_turn(b"b", "turn.webm", "audio/webm"))
    assert len(orch.turns) == 1, "the continuation reuses the same turn"
    assert orch.turns[0].user_text == "Erste Haelfte. Und der Rest."
    assert any(isinstance(e, AudioChunk) for e in events)


async def test_new_or_reopened_turn_bookkeeping(persona, scenario):
    orch = SessionOrchestrator(persona, scenario)
    t1, reopening1 = orch._new_or_reopened_turn()
    assert reopening1 is False and t1.seq == 1 and orch.turns == [t1]

    t2, reopening2 = orch._new_or_reopened_turn()
    assert reopening2 is True and t2 is t1, "still-open turn is reused"
    assert orch.turns == [t1], "no second turn was appended"
