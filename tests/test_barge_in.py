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

# pylint: disable=duplicate-code
# Fixture data is repeated per test module on purpose: a test carrying its own
# Turns shows what it ran against when it fails, and sharing them would let a
# change made for one test quietly alter another.


import asyncio

import pytest

from backend.session.models import AudioChunk, StateChanged, TurnCompleted, utterances
from backend.session.nudges import INTERRUPTED_MARK, strip_interrupted_mark
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
    assert orch._messages[-1] == {"role": "assistant", "content": heard + INTERRUPTED_MARK}, "history in step"
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
    assert orch._messages[-1] == {"role": "assistant", "content": heard + INTERRUPTED_MARK}

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
    assert orch._messages[-1] == {"role": "assistant", "content": s1 + INTERRUPTED_MARK}
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
    assert orch._messages[-1]["content"] == heard + INTERRUPTED_MARK, "history trimmed in step"


async def test_a_cut_off_persona_line_is_marked_in_the_transcript(
    persona, scenario, fake_pipeline, monkeypatch
):
    """A Persona line the user talked over ends with "[unterbrochen]" in the
    transcript -- but `persona_text` itself, which the metrics read, stays
    clean, and the LLM history gets only the cut-off dash (ADR 0035)."""
    monkeypatch.setattr("backend.session.orchestrator.tts.duration_ms", lambda _wav: 10000)
    sentence = (
        "Ich wollte mich eigentlich nur ganz kurz erkundigen ob der vereinbarte "
        "Termin am Donnerstag naechster Woche so wie besprochen noch steht."
    )
    fake_pipeline.stt.transcripts = ["Bitte."]
    fake_pipeline.llm.replies = [sentence]

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))
    orch.note_late_barge_in(2000)  # cut short, a word-prefix is kept

    turn = orch.turns[0]
    assert turn.persona_interrupted is True
    assert not turn.persona_text.endswith("[unterbrochen]"), "the raw text stays clean"
    assert orch._messages[-1]["content"] == turn.persona_text + INTERRUPTED_MARK
    assert "[unterbrochen]" not in orch._messages[-1]["content"], "no bracket token for the model"

    persona_line = next(u.text for u in utterances(orch.turns) if u.speaker == "persona")
    assert persona_line == f"{turn.persona_text} ... [unterbrochen]"


async def test_the_turn_after_an_interruption_tells_the_model_where_it_was_cut_off(
    persona, scenario, fake_pipeline, monkeypatch
):
    """Handed a bare fragment as "its previous reply", the model tried to finish
    the sentence or re-introduced itself. The next Turn therefore carries a
    nudge naming the interruption and quoting the fragment, in place of the
    anti-repeat nudge -- and only that one Turn (ADR 0035, ADR 0038)."""
    monkeypatch.setattr("backend.session.orchestrator.tts.duration_ms", lambda _wav: 10000)
    opening = (
        "Guten Tag, ich bin Thomas Brandt von der Firma Insight Analytics und "
        "rufe wegen unserer letzten Abrechnung an, da ist etwas unklar."
    )
    fake_pipeline.stt.transcripts = ["Moment, worum geht es genau?", "Verstehe, und was schlagen Sie vor?"]
    fake_pipeline.llm.replies = [
        opening,
        "Es geht um die Rechnung vom Maerz, da stimmt der Betrag nicht mit dem Vertrag ueberein.",
        "Ich schlage vor, Sie pruefen den Posten und melden sich bis Freitag bei mir zurueck.",
    ]

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_opening_turn())
    orch.note_late_barge_in(2000)  # a few words in
    fragment = orch.turns[0].persona_text
    assert opening.startswith(fragment) and fragment != opening

    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))
    assert not any(isinstance(e, TurnCompleted) and e.ends_call for e in events), "the call goes on"
    sent = fake_pipeline.llm.calls[-1]
    assert sent[1]["content"] == fragment + INTERRUPTED_MARK, "the history line is marked"
    # The nudge sits between the dashed line and the user's message, and quotes
    # nothing: what the model sees last is the user's message, not the fragment.
    assert [m["role"] for m in sent[1:]] == ["assistant", "system", "user"]
    assert "cut you off" in sent[2]["content"] and fragment not in sent[2]["content"]
    assert sent[3]["content"] == "Moment, worum geht es genau?"
    assert not any("Your previous reply in this call was" in m["content"] for m in sent), "anti-repeat nudge replaced"

    await collect(orch.run_turn(b"b", "turn.webm", "audio/webm"))
    systems = [m["content"] for m in fake_pipeline.llm.calls[-1] if m["role"] == "system"]
    assert not any("cut you off" in s for s in systems), "only the one Turn"
    assert any("Your previous reply in this call was" in s for s in systems), "back to the standing nudge"


async def test_a_reply_that_reads_the_users_line_back_is_cut_to_the_answer(
    persona, scenario, fake_pipeline, monkeypatch
):
    """Seen live on the Turn after a barge-in: the model opened by reciting the
    user's question ("Verzeihung, mit wem rede ich da? Ich bin Thomas ...").
    The echo is dropped before synthesis, so neither the speakers nor the
    history nor the Transcript get it -- and the re-introduction guard still
    looks at the first chunk that has words in it."""
    monkeypatch.setattr("backend.session.orchestrator.tts.duration_ms", lambda _wav: 10000)
    question = "Verzeihung, mit wem rede ich da?"
    answer = "Ich bin Thomas Brandt, Managing Director bei Insight Analytics, es geht um unseren Vertrag."
    fake_pipeline.stt.transcripts = [question]
    fake_pipeline.llm.replies = [
        "Guten Tag, ich bin Thomas Brandt von der Firma Insight Analytics, ich rufe wegen einer Rechnung an.",
        f"{question} {answer}",
    ]

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_opening_turn())
    orch.note_late_barge_in(1500)  # "Guten Tag, ich bin ..." -- the live case
    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    assert orch.turns[1].persona_text == answer
    assert question not in orch._messages[-1]["content"]
    assert any(isinstance(e, AudioChunk) for e in events), "the answer itself is spoken"
    persona_lines = [u.text for u in utterances(orch.turns) if u.speaker == "persona"]
    assert not any(line.startswith(question) for line in persona_lines)


# --- The cut-off sentence must not come back in any form (ADR 0035) --------
#
# Live, three times in one day: after a barge-in the model's next reply began
# with the sentence the user had just talked over -- finished this time -- and
# only then said what it had to say. Verbatim repeats are the dedup's; these
# are the two forms it cannot see: the sentence restarted from the top, and its
# tail continued mid-sentence.

_FIRST = "Das ist okay, aber ich will den Termin vor dem 8. September."
_CUT = "Sagen Sie mir, bis wann Sie das dann genau schaffen?"


async def _cut_off_reply(orch, fake_pipeline, monkeypatch, reply=f"{_FIRST} {_CUT}", played_ms=14000):
    """One reply the user talks over: the first sentence heard whole, the
    second cut five words in (each chunk 10 s; 14 s + grace is 43% of it) --
    enough of a fragment for `repetition.resumes` to match on."""
    monkeypatch.setattr("backend.session.orchestrator.tts.duration_ms", lambda _wav: 10000)
    fake_pipeline.stt.transcripts.insert(0, "Was ist denn genau das Problem?")
    fake_pipeline.llm.replies.insert(0, reply)
    await collect(orch.run_turn(b"0", "turn.webm", "audio/webm"))
    orch.note_late_barge_in(played_ms)
    heard = orch.turns[0].persona_text
    fragment = heard[len(_FIRST):].strip()
    assert heard.startswith(_FIRST) and heard != reply and _CUT.startswith(fragment)
    assert len(fragment.split()) >= 3, "the fragment the filter matches on"
    return heard


async def test_the_cut_off_sentence_restarted_from_the_top_is_dropped(persona, scenario, fake_pipeline, monkeypatch):
    fake_pipeline.stt.transcripts = ["Heute ist der sechste, das passt nicht mehr."]
    fake_pipeline.llm.replies = [f"{_CUT} Dann nehme ich den Freitag."]
    orch = SessionOrchestrator(persona, scenario)
    await _cut_off_reply(orch, fake_pipeline, monkeypatch)

    events = await collect(orch.run_turn(b"1", "turn.webm", "audio/webm"))

    assert not any(isinstance(e, TurnCompleted) and e.ends_call for e in events)
    assert orch.turns[1].persona_text == "Dann nehme ich den Freitag."
    assert len(fake_pipeline.llm.calls) == 2, "dropped, not regenerated: the rest of the reply was fine"


async def test_the_cut_off_sentence_continued_mid_sentence_is_dropped(persona, scenario, fake_pipeline, monkeypatch):
    fake_pipeline.stt.transcripts = ["Moment, was schlagen Sie denn konkret vor?"]
    fake_pipeline.llm.replies = ["genau schaffen? Ich hoere Ihnen zu, was schlagen Sie vor?"]
    orch = SessionOrchestrator(persona, scenario)
    await _cut_off_reply(orch, fake_pipeline, monkeypatch)

    await collect(orch.run_turn(b"1", "turn.webm", "audio/webm"))

    assert orch.turns[1].persona_text == "Ich hoere Ihnen zu, was schlagen Sie vor?"


async def test_a_reply_that_is_nothing_but_the_cut_off_sentence_is_re_asked_once(
    persona, scenario, fake_pipeline, monkeypatch
):
    fake_pipeline.stt.transcripts = ["Heute ist der sechste, das passt nicht mehr."]
    fake_pipeline.llm.replies = [_CUT, "Freitag passt mir, danke."]
    orch = SessionOrchestrator(persona, scenario)
    await _cut_off_reply(orch, fake_pipeline, monkeypatch)

    events = await collect(orch.run_turn(b"1", "turn.webm", "audio/webm"))

    assert not any(isinstance(e, TurnCompleted) and e.ends_call for e in events)
    assert len(fake_pipeline.llm.calls) == 3, "one re-ask"
    nudge = fake_pipeline.llm.calls[-1][-1]
    assert nudge["role"] == "system" and "picked the sentence the user cut off back up" in nudge["content"]
    assert _CUT in nudge["content"]
    assert orch.turns[1].persona_text == "Freitag passt mir, danke."
    assert _CUT not in orch._messages[-1]["content"]


async def test_re_delivering_the_cut_off_sentences_after_a_barge_in_is_trimmed_not_ended(
    persona, scenario, fake_pipeline, monkeypatch
):
    """After a barge-in the model tends to re-deliver the sentences the user
    already heard before getting to anything new. Those are dropped from the
    chunk before it is spoken -- the user hears only the new part -- and the
    call goes on, rather than ADR 0038's restatement backstop ending it."""
    monkeypatch.setattr("backend.session.orchestrator.tts.duration_ms", lambda _wav: 1000)
    # Each >= 80 chars so the chunker flushes all three as their own chunks.
    a = "Die Rechnung vom Maerz weist vierzehn Lizenzen aus, wir nutzen aber tatsaechlich nur acht davon."
    b = "Und der Preis pro Lizenz ist seit dem Vertragsabschluss um ganze zwoelf Prozent gestiegen worden."
    c = "Deshalb moechte ich von Ihnen wissen, ob wir den Vertrag entsprechend anpassen koennen, bitte."
    assert min(len(a), len(b), len(c)) >= 80
    fake_pipeline.stt.transcripts = ["Moment, langsam bitte.", "Okay."]
    # The resumption opens with a short lead-in, not with a sentence already
    # said (that would be a repeated opening, regenerated -- ADR 0038), then
    # re-delivers a and b, then says something new.
    fake_pipeline.llm.replies = [
        f"{a} {b} {c}",
        f"Wie gesagt. {a} {b} Koennen wir das gemeinsam durchgehen, bitte?",
        "Gut, dann warte ich auf Ihre Rueckmeldung.",
    ]

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))
    orch.note_late_barge_in(2200)  # all of a and b, half of c
    assert orch.turns[0].persona_text.startswith(f"{a} {b}")
    assert c not in orch.turns[0].persona_text

    events = await collect(orch.run_turn(b"b", "turn.webm", "audio/webm"))
    assert not any(isinstance(e, TurnCompleted) and e.ends_call for e in events), "the call goes on"
    assert orch.turns[1].persona_text == "Wie gesagt. Koennen wir das gemeinsam durchgehen, bitte?"
    assert a not in orch.turns[1].persona_text and b not in orch.turns[1].persona_text
    assert len(fake_pipeline.llm.calls) == 2, "spoken as generated, no regeneration"


async def test_a_fully_heard_persona_line_is_not_marked(persona, scenario, fake_pipeline):
    """No barge-in -> no marker."""
    fake_pipeline.stt.transcripts = ["Bitte erklaeren Sie mir das."]
    fake_pipeline.llm.replies = ["Eine ganz normale, vollstaendig gehoerte Antwort."]

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    assert orch.turns[0].persona_interrupted is False
    persona_line = next(u.text for u in utterances(orch.turns) if u.speaker == "persona")
    assert "[unterbrochen]" not in persona_line


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Ich will—", "Ich will"),                       # the live case: a copied history line
        ("Das ist so. Ich will— und zwar jetzt.", "Das ist so. Ich will und zwar jetzt."),
        ("Ganz normal, ohne Strich.", "Ganz normal, ohne Strich."),
        ("——", ""),
    ],
)
def test_strip_interrupted_mark(text, expected):
    assert strip_interrupted_mark(text) == expected


async def test_new_or_reopened_turn_bookkeeping(persona, scenario):
    orch = SessionOrchestrator(persona, scenario)
    t1, reopening1 = orch._new_or_reopened_turn()
    assert reopening1 is False and t1.seq == 1 and orch.turns == [t1]

    t2, reopening2 = orch._new_or_reopened_turn()
    assert reopening2 is True and t2 is t1, "still-open turn is reused"
    assert orch.turns == [t1], "no second turn was appended"
