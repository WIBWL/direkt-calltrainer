"""The live session loop: STT -> streamed dialogue -> chunked TTS per turn.

Covers:
  F-46  Live-Call-Interface: the listening / thinking / speaking state model
  F-01  the persona opens the call and then responds turn by turn
  F-12/F-52/R-52  the full transcript is assembled from the turns, and only
        at the end (nothing partial is exposed mid-call)
  ADR 0033  streamed pipeline: audio is produced chunk by chunk, first chunk
        before the whole reply is finished
"""

import pytest

from backend.session.models import AudioChunk, StateChanged, TurnCompleted
from backend.session.orchestrator import SessionOrchestrator
from tests.conftest import audio_chunks, collect, completed, states

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
