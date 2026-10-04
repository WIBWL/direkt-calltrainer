"""The live session loop: STT -> streamed dialogue -> chunked TTS per turn.

Covers F-46 (listening/thinking/speaking), F-01 (persona opens, then turn by turn),
ADR 0110 (in an ordinary call the user picks up first; a reverse keeps its own opening),
F-12/F-52/R-52 (transcript only at the end), ADR 0033 (first audio chunk before the reply ends),
ADR 0047/0048 (per-Turn acoustics inline and on failure; statistics: shared/tests/test_metrics.py)."""

import asyncio
from dataclasses import replace

import pytest

from shared.feedback.acoustics import AcousticsError, TurnAcoustics
from shared.turn import Turn
from backend.session.events import AudioChunk, StateChanged, TurnCompleted
from backend.session.measuring import attach_measurements
from backend.session.orchestrator import SessionOrchestrator
from backend.tests.conftest import audio_chunks, collect, completed, failure, states

# pylint: disable=missing-function-docstring,redefined-outer-name


@pytest.fixture
def orch(persona, scenario):
    return SessionOrchestrator(persona, scenario)


async def test_persona_opens_the_call_itself(orch, fake_pipeline):
    """F-01: the persona speaks first, with no user audio submitted."""
    fake_pipeline.llm.replies = ["Guten Tag, hier ist Thomas Brandt von der Beispiel GmbH."]
    events = await collect(orch.run_opening_turn())

    assert states(events)[0] == "thinking"
    assert "speaking" in states(events)
    assert audio_chunks(events), "the opening line is synthesized to audio"
    assert orch.turns[0].seq == 1
    assert orch.turns[0].persona_text == "Guten Tag, hier ist Thomas Brandt von der Beispiel GmbH."
    assert orch.turns[0].user_text == ""
    assert not fake_pipeline.stt.calls, "opening turn does not transcribe anything"


async def test_turn_runs_stt_then_llm_then_tts_and_reports_state(orch, fake_pipeline):
    """F-46: a normal turn goes thinking -> speaking -> back to listening."""
    fake_pipeline.stt.transcripts = ["Ich glaube, das Angebot passt so."]
    fake_pipeline.llm.replies = ["Gut. Dann brauche ich noch die genaue Laufzeit von Ihnen."]

    events = await collect(orch.run_turn(b"webm-bytes", "turn.webm", "audio/webm"))

    assert states(events) == ["thinking", "speaking", "listening"]
    assert fake_pipeline.stt.calls[0][0] == b"webm-bytes"
    assert fake_pipeline.stt.calls[0][3] == "de"  # persona language passed to STT
    tc = completed(events)
    assert isinstance(tc, TurnCompleted) and tc.ends_call is False


async def test_reply_audio_streams_in_multiple_chunks(orch, fake_pipeline):
    """ADR 0033: a long reply is synthesized and sent as several ordered
    chunks rather than one blob at the end."""
    fake_pipeline.stt.transcripts = ["Erklaeren Sie mir bitte einmal die Details."]
    long_reply = (
        "Der erste Punkt betrifft die Vertragslaufzeit, die bei zwoelf Monaten liegt. "
        "Der zweite Punkt ist der monatliche Grundpreis von neunundneunzig Euro. "
        "Und drittens kommt die einmalige Einrichtungsgebuehr noch dazu."
    )
    fake_pipeline.llm.replies = [long_reply]

    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))
    chunks = audio_chunks(events)

    assert len(chunks) >= 2
    assert [c.chunk_seq for c in chunks] == list(range(1, len(chunks) + 1))
    assert all(c.turn_seq == 1 for c in chunks)
    # every synthesized chunk is non-empty audio
    assert all(c.audio.startswith(b"AUDIO:") for c in chunks)


async def test_thinking_is_emitted_before_any_audio(orch, fake_pipeline):
    """F-46 / ADR 0033: 'thinking' shows while the first chunk is still being
    generated; 'speaking' only once real audio is ready."""
    fake_pipeline.stt.transcripts = ["Kurze Frage."]
    fake_pipeline.llm.replies = ["Eine kurze, klare Antwort dazu."]

    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))
    kinds = [
        "thinking" if isinstance(e, StateChanged) and e.state == "thinking"
        else "speaking" if isinstance(e, StateChanged) and e.state == "speaking"
        else "audio" if isinstance(e, AudioChunk)
        else None
        for e in events
    ]
    kinds = [k for k in kinds if k]
    assert kinds.index("thinking") < kinds.index("speaking") < kinds.index("audio")


async def test_transcript_is_assembled_across_turns_at_the_end(orch, fake_pipeline):
    """F-12/R-52: after several turns, orchestrator.turns holds the complete
    user+persona transcript, ready to be sent once when the session ends."""
    fake_pipeline.llm.replies = [
        "Guten Tag, ich rufe wegen unseres Vertrags an.",
        "Verstehe. Und was genau ist da unklar?",
        "Alles klar, das passt fuer mich.",
    ]
    fake_pipeline.stt.transcripts = [
        "Hallo, ja, es geht um die Abrechnung.",
        "Die letzte Rechnung war doppelt so hoch wie sonst.",
    ]

    await collect(orch.run_opening_turn())
    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))
    await collect(orch.run_turn(b"b", "turn.webm", "audio/webm"))

    transcript = [
        {"turn_seq": t.seq, "user_text": t.user_text, "persona_text": t.persona_text}
        for t in orch.turns
    ]
    assert transcript == [
        {"turn_seq": 1, "user_text": "", "persona_text": "Guten Tag, ich rufe wegen unseres Vertrags an."},
        {
            "turn_seq": 2,
            "user_text": "Hallo, ja, es geht um die Abrechnung.",
            "persona_text": "Verstehe. Und was genau ist da unklar?",
        },
        {
            "turn_seq": 3,
            "user_text": "Die letzte Rechnung war doppelt so hoch wie sonst.",
            "persona_text": "Alles klar, das passt fuer mich.",
        },
    ]


async def test_a_measured_turn_records_both_its_durations(orch, fake_pipeline, monkeypatch):
    """ADR 0047/0048. A recording that ran 1.5 s and held 0.9 s of speech puts
    both figures on the Turn, in their own fields: the recording's length is
    kept as the fact it is, speaking pace divides by the second."""
    monkeypatch.setattr(
        "backend.session.orchestrator.analyze",
        # Every field named, including the empty curves: TurnAcoustics carries
        # no defaults, so a new measurement cannot be added without every
        # construction of it being revisited.
        lambda _audio: TurnAcoustics(
            duration_ms=1500, phonation_ms=900, voice_start_ms=300, voice_end_ms=1200,
            pauses=(), loudness_db=(), pitch_hz=(),
        ),
    )
    fake_pipeline.stt.transcripts = ["Ich spreche mit einer Pause."]
    fake_pipeline.llm.replies = ["Danke fuer die Information."]

    await collect(orch.run_turn(b"audio", "turn.wav", "audio/wav"))

    assert orch.turns[0].user_speech_ms == 1500
    assert orch.turns[0].user_phonation_ms == 900
    assert orch.turns[0].user_acoustics_complete is True


def _measured(duration_ms: int, voice_start_ms: int, voice_end_ms: int) -> TurnAcoustics:
    """A recording whose sound runs from `voice_start_ms` to `voice_end_ms`."""
    return TurnAcoustics(
        duration_ms=duration_ms, phonation_ms=voice_end_ms - voice_start_ms,
        voice_start_ms=voice_start_ms, voice_end_ms=voice_end_ms,
        pauses=(), loudness_db=(), pitch_hz=(),
    )


async def _done(acoustics: TurnAcoustics) -> "asyncio.Task[TurnAcoustics]":
    return asyncio.create_task(asyncio.sleep(0, result=acoustics))


async def test_a_reply_is_placed_at_its_first_sound_not_at_the_recording():
    """ADR 0114. A 2.8 s recording that arrived at 10 s began at 7.2 s, but its
    first 0.8 s are the VAD's lead-in and its last second the silence it waited
    through: the user spoke from 8.0 s to 9.0 s. Placed on the recording's
    edges, every reply started 0.8 s early -- a reaction time short by that
    much and a start inside the Persona's line that never happened."""
    turn = Turn(seq=1)

    await attach_measurements(turn, await _done(_measured(2_800, 800, 1_800)), ended_ms=10_000)

    assert (turn.user_offset_ms, turn.user_end_ms) == (8_000, 9_000)
    # The pauses' offsets are relative to the recording, so they stay rebased
    # on its start; only the utterance's own edges move.
    assert turn.user_speech_ms == 2_800


async def test_a_continued_turn_keeps_its_first_sound_and_takes_the_last():
    """A Turn reopened after a barge-in (ADR 0035) begins where its first
    fragment's sound began and ends where its last fragment's sound ended."""
    turn = Turn(seq=1)

    await attach_measurements(turn, await _done(_measured(2_800, 800, 1_800)), ended_ms=10_000)
    await attach_measurements(turn, await _done(_measured(2_500, 700, 1_500)), ended_ms=14_000)

    assert (turn.user_offset_ms, turn.user_end_ms) == (8_000, 13_000)


@pytest.mark.parametrize(
    "error",
    [
        AcousticsError("audio too short to analyze"),
        RuntimeError("something from the Praat C extension"),
    ],
    ids=["measurement_declined", "unexpected_failure"],
)
async def test_an_unmeasurable_turn_says_so(orch, fake_pipeline, monkeypatch, error):
    """ADR 0048. Both failure paths -- the one `analyze` raises deliberately and
    the catch-all for whatever Praat's C extension surfaces -- flag the Turn
    rather than only logging. The call carries on: this leg is never
    load-bearing."""
    def fail_analyze(_audio):
        raise error

    monkeypatch.setattr("backend.session.orchestrator.analyze", fail_analyze)
    fake_pipeline.stt.transcripts = ["Ich spreche trotz Messfehler."]
    fake_pipeline.llm.replies = ["Danke fuer die Information."]

    events = await collect(orch.run_turn(b"audio", "turn.wav", "audio/wav"))

    assert orch.turns[0].user_acoustics_complete is False
    assert orch.turns[0].user_speech_ms == 0
    assert orch.turns[0].user_phonation_ms == 0
    # An unmeasurable Turn is not a failed one.
    assert completed(events) is not None
    assert orch.turns[0].persona_text == "Danke fuer die Information."


async def test_empty_llm_reply_fails_after_retry(orch, fake_pipeline):
    """An empty model response must not complete the Turn successfully."""
    fake_pipeline.stt.transcripts = ["Bitte erklären Sie mir das."]
    fake_pipeline.llm.replies = ["", ""]

    events = await collect(
        orch.run_turn(b"a", "turn.webm", "audio/webm")
    )

    assert len(fake_pipeline.llm.calls) == 2
    assert failure(events) is not None
    assert failure(events).code == "llm_failed"
    assert completed(events) is None
    assert not audio_chunks(events)


async def test_tts_zero_audio_fails_turn(orch, fake_pipeline):
    """A TTS stream without audio must not complete the Turn successfully."""
    fake_pipeline.stt.transcripts = ["Bitte erklären Sie mir das."]
    fake_pipeline.llm.replies = ["Natürlich, ich erkläre es Ihnen."]
    fake_pipeline.tts.chunks_per_call = 0

    events = await collect(
        orch.run_turn(b"a", "turn.webm", "audio/webm")
    )

    assert failure(events) is not None
    assert failure(events).code == "tts_failed"
    assert completed(events) is None
    assert not audio_chunks(events)


# --- ADR 0110: the user picks up ------------------------------------------


async def test_an_ordinary_call_opens_with_the_reply_to_the_users_answering_line(orch, fake_pipeline):
    """ADR 0110: the Persona rang, so the user answers first and the Persona's
    first words are the reply to that -- asked for by the opening instruction,
    placed after the user's line so it is what the model reads last."""
    fake_pipeline.stt.transcripts = ["Beispiel GmbH, Müller am Apparat, guten Tag."]
    fake_pipeline.llm.replies = ["Guten Tag Herr Müller, hier ist Thomas Brandt. Es geht um meinen Vertrag."]

    events = await collect(orch.run_turn(b"webm-bytes", "turn.webm", "audio/webm"))

    sent = fake_pipeline.llm.calls[0]
    assert sent[-2] == {"role": "user", "content": "Beispiel GmbH, Müller am Apparat, guten Tag."}
    assert sent[-1]["role"] == "system"
    assert "the user has just picked up" in sent[-1]["content"]
    # The greeting is the opening here, so the re-greeting guard lets it through.
    assert len(fake_pipeline.llm.calls) == 1
    assert audio_chunks(events)
    assert orch.turns[0].user_text == "Beispiel GmbH, Müller am Apparat, guten Tag."
    assert orch.turns[0].persona_text.startswith("Guten Tag Herr Müller")


async def test_the_opening_instruction_is_spent_once_the_persona_has_been_heard(orch, fake_pipeline):
    fake_pipeline.stt.transcripts = ["Müller, guten Tag.", "Worum geht es genau?"]
    fake_pipeline.llm.replies = ["Hallo, hier ist Thomas Brandt wegen meines Vertrags.", "Um die Laufzeit."]

    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))
    await collect(orch.run_turn(b"b", "turn.webm", "audio/webm"))

    second = fake_pipeline.llm.calls[1]
    assert not any("the user has just picked up" in m["content"] for m in second)


async def test_a_reverse_never_gets_the_callers_opening_instruction(persona, scenario, fake_pipeline):
    """In a reverse the Persona picked up; the caller's opener would cast it
    as the one ringing (ADR 0070)."""
    orch = SessionOrchestrator(persona, replace(scenario, reverse=True))
    fake_pipeline.stt.transcripts = ["Guten Tag, ich rufe wegen meiner Rechnung an."]
    fake_pipeline.llm.replies = ["Gern, worum geht es denn?"]

    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    assert not any("the user has just picked up" in m["content"] for m in fake_pipeline.llm.calls[0])
