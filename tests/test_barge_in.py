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


async def test_interrupt_commits_only_what_played_through(persona, scenario, fake_pipeline, monkeypatch):
    """The client reports how many ms of the reply it actually played; only the
    audio inside that window reaches the history -- every fully-played sentence
    plus a word-prefix of the one the user cut off -- even though the server had
    already streamed the whole reply ahead (ADR 0035)."""
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

    orch.note_barge_in(1200)  # 1.0s (all of s1) + 0.2s into s2
    await gen.aclose()

    heard = orch.turns[0].persona_text
    assert heard.startswith(s1), "the fully-played first sentence is kept whole"
    assert s3 not in heard, "the third sentence was streamed ahead but never played"
    assert heard != f"{s1} {s2} {s3}" and len(heard) < len(f"{s1} {s2}"), "s2 only partially"
    assert s2.startswith(heard[len(s1):].strip()), "the s2 fragment is a word-prefix of s2"
    assert orch._messages[-1] == {"role": "assistant", "content": heard}, "history in step"
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


async def test_a_sentence_heard_almost_to_its_end_keeps_almost_all_of_it(
    persona, scenario, fake_pipeline, monkeypatch
):
    """Cutting in a moment before a sentence finishes keeps almost all of its
    words and closes the turn -- the fraction of its audio that played maps
    onto the fraction of its words kept (ADR 0035)."""
    monkeypatch.setattr("backend.session.orchestrator.tts.duration_ms", lambda _wav: 5000)
    s1 = "Der erste Satz meiner Antwort ist inhaltlich vollstaendig und lang genug fuer seinen eigenen Chunk."
    s2 = "Den zweiten Satz hoert der Nutzer gar nicht mehr, weil er kurz vorher schon dazwischenredet."
    assert min(len(s1), len(s2)) >= 80
    fake_pipeline.stt.transcripts = ["Bitte erklaeren Sie mir das.", "Was war der erste Satz?"]
    fake_pipeline.llm.replies = [f"{s1} {s2}", "Kurz gesagt: es geht um den Preis."]

    orch = SessionOrchestrator(persona, scenario)
    gen = orch.run_turn(b"a", "turn.webm", "audio/webm")
    # Drain past the second chunk's audio so the first chunk's checkpoint is
    # recorded (it lands after that chunk's audio loop finishes).
    seen = 0
    async for event in gen:
        if isinstance(event, AudioChunk):
            seen += 1
            if seen == 2:
                break
    orch.note_barge_in(4400)  # ~88% + 0.3s grace = ~94% through the 5s first sentence
    await gen.aclose()

    heard = orch.turns[0].persona_text
    assert s1.startswith(heard) and heard != s1, "almost all of s1, but not quite"
    assert len(heard) >= 0.8 * len(s1)
    assert s2 not in heard
    assert orch._reopen_turn is None, "a word was heard, so the turn is closed"
    assert orch._messages[-1] == {"role": "assistant", "content": heard}

    events = await collect(orch.run_turn(b"b", "turn.webm", "audio/webm"))
    assert len(orch.turns) == 2, "the reaction is its own turn, not merged onto the first"
    assert orch.turns[1].user_text == "Was war der erste Satz?"
    assert any(isinstance(e, AudioChunk) for e in events)


async def test_late_barge_in_trims_a_completed_reply_to_what_was_heard(
    persona, scenario, fake_pipeline, monkeypatch
):
    """The reply finished and was committed here while the client was still
    playing its tail; the `turn.interrupt` only reaches the server now, between
    turns. It must still trim the stored reply -- and the Transcript -- down to
    the part that was actually played (ADR 0035)."""
    monkeypatch.setattr("backend.session.orchestrator.tts.duration_ms", lambda _wav: 1000)
    s1 = "Der erste Satz meiner Antwort ist inhaltlich vollstaendig und lang genug fuer seinen eigenen Chunk."
    s2 = "Der zweite Satz folgt unmittelbar darauf und ist ebenfalls lang genug fuer einen eigenen Chunk hier."
    fake_pipeline.stt.transcripts = ["Bitte erklaeren Sie mir das."]
    fake_pipeline.llm.replies = [f"{s1} {s2}"]

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))
    assert orch.turns[0].persona_text == f"{s1} {s2}", "the whole reply is committed first"

    orch.note_late_barge_in(700)  # 0.7s + 0.3s grace = exactly the first sentence

    assert orch.turns[0].persona_text == s1
    assert orch._messages[-1] == {"role": "assistant", "content": s1}
    assert orch._reopen_turn is None

    # A second stray interrupt (played_ms now ~0) must not erase what is left.
    orch.note_late_barge_in(0)
    assert orch.turns[0].persona_text == s1


async def test_late_barge_in_with_nothing_heard_reopens_the_turn(
    persona, scenario, fake_pipeline, monkeypatch
):
    """If the late interrupt reports that essentially none of the reply played,
    the committed reply is dropped and the turn reopens, so the next utterance
    continues the same question."""
    monkeypatch.setattr("backend.session.orchestrator.tts.duration_ms", lambda _wav: 30000)
    s1 = "Ein einziger, inhaltlich vollstaendiger Satz der lang genug fuer seinen eigenen Chunk ist hier jetzt."
    fake_pipeline.stt.transcripts = ["Erste Haelfte.", "Und der Rest."]
    fake_pipeline.llm.replies = [s1, "Die echte Antwort."]

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    orch.note_late_barge_in(80)  # 0.4s into a 30s sentence -> not even the first word

    assert orch.turns[0].persona_text == ""
    assert not [m for m in orch._messages if m["role"] == "assistant"]
    assert orch._reopen_turn is orch.turns[0]

    await collect(orch.run_turn(b"b", "turn.webm", "audio/webm"))
    assert len(orch.turns) == 1, "the continuation reuses the same turn"
    assert orch.turns[0].user_text == "Erste Haelfte. Und der Rest."


async def test_a_barge_in_mid_sentence_trims_the_transcript_to_the_word(
    persona, scenario, fake_pipeline, monkeypatch
):
    """Cutting in three words into a long sentence leaves roughly those three
    words in the transcript, not the whole sentence (ADR 0035)."""
    monkeypatch.setattr("backend.session.orchestrator.tts.duration_ms", lambda _wav: 10000)
    sentence = (
        "Ich wollte mich eigentlich nur ganz kurz erkundigen ob der vereinbarte "
        "Termin am Donnerstag naechster Woche so wie besprochen noch steht."
    )
    fake_pipeline.stt.transcripts = ["Bitte."]
    fake_pipeline.llm.replies = [sentence]

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))
    assert orch.turns[0].persona_text == sentence

    orch.note_late_barge_in(2000)  # ~2.3s of a 10s sentence -> the opening words

    heard = orch.turns[0].persona_text
    assert sentence.startswith(heard), "a leading word-prefix of the sentence"
    assert 0 < len(heard) < len(sentence) // 2, "clearly cut short, not the whole sentence"
    assert heard == heard.strip() and sentence[len(heard)] == " ", "ends on a whole word"
    assert orch._messages[-1]["content"] == heard, "history trimmed in step"


async def test_new_or_reopened_turn_bookkeeping(persona, scenario):
    orch = SessionOrchestrator(persona, scenario)
    t1, reopening1 = orch._new_or_reopened_turn()
    assert reopening1 is False and t1.seq == 1 and orch.turns == [t1]

    t2, reopening2 = orch._new_or_reopened_turn()
    assert reopening2 is True and t2 is t1, "still-open turn is reused"
    assert orch.turns == [t1], "no second turn was appended"
