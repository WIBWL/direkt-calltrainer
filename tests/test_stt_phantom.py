"""Whisper's phantom transcripts do not become Turns (ADR 0071; the guard
docs/research/model-parameters.md left open).

On near-silence Whisper invents a phrase -- "Vielen Dank.", "Amen.", a
subtitle credit -- or a non-speech annotation like "*Titelm*" or "[Musik]".
One such 9-character transcript became a real Turn in a live call and derailed
the persona. A transcript that is nothing but one of these gets no reply and
no history entry; the Session returns to listening.
"""

import pytest

from backend.session.language_packs import get_pack, is_phantom
from backend.session.models import AudioChunk, StateChanged
from backend.session.orchestrator import SessionOrchestrator
from tests.conftest import collect

# pylint: disable=missing-function-docstring,protected-access

GERMAN = get_pack("de")
ENGLISH = get_pack("en")


@pytest.mark.parametrize(
    "text",
    ["*Titelm*", "[Musik]", "(Applaus)", "Vielen Dank.", " Vielen Dank fürs Zuschauen! ", "Amen.",
     "Untertitelung des ZDF, 2020", "Untertitel von Stephanie Geiges", "", "   "],
)
def test_german_phantoms_are_recognised(text):
    assert is_phantom(GERMAN, text) is True


@pytest.mark.parametrize(
    "text",
    ["Ja.", "Nein.", "Danke.", "Nein, danke, das passt so.", "Vielen Dank für die Info, und wann geht der Export?",
     "Moment, ich schaue nach.", "Titel des Tickets ist Exportfehler."],
)
def test_real_answers_are_not(text):
    assert is_phantom(GERMAN, text) is False


@pytest.mark.parametrize(
    "text", ["Thank you.", "Thanks for watching!", "Subtitles by the Amara.org community", "[Music]"]
)
def test_english_phantoms_are_recognised(text):
    assert is_phantom(ENGLISH, text) is True


async def test_a_phantom_transcript_is_no_turn(persona, scenario, fake_pipeline):
    fake_pipeline.stt.transcripts = ["*Titelm*", "So, jetzt bin ich wieder da, worum ging es?"]
    fake_pipeline.llm.replies = ["Es geht um die Exportfunktion, die seit elf Tagen nicht funktioniert."]

    orch = SessionOrchestrator(persona, scenario)
    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    assert not any(isinstance(e, AudioChunk) for e in events), "nothing is said"
    assert isinstance(events[-1], StateChanged) and events[-1].state == "listening"
    assert not fake_pipeline.llm.calls, "no reply was even asked for"
    assert not orch.turns and orch.history.messages[-1]["role"] == "system", "no Turn, no history entry"

    events = await collect(orch.run_turn(b"b", "turn.webm", "audio/webm"))
    assert any(isinstance(e, AudioChunk) for e in events), "the next real utterance is a Turn as usual"
    assert len(orch.turns) == 1 and orch.turns[0].seq == 1


async def test_a_phantom_on_a_reopened_turn_does_not_stretch_the_user_window(
    persona, scenario, fake_pipeline, monkeypatch
):
    """A phantom after a barge-in leaves the reopened Turn exactly as it was.

    A fresh Turn is popped when the transcript turns out to be a phantom, but a
    reopened one has to stay -- it still holds the question the user was in the
    middle of. Its end was being written before the phantom check, so a cough
    transcribed as "Vielen Dank." pushed `user_end_ms` out to the cough while
    the measured speaking time stayed where it was. That span is the
    utterance's duration in the Transcript and on the timeline F-51 reads its
    overlaps off, so it would have run from the user's first word to a noise
    seconds later.
    """
    monkeypatch.setattr("backend.session.orchestrator.tts.duration_ms", lambda _wav: 100000)
    fake_pipeline.stt.transcripts = ["Erste Haelfte der Frage.", "Vielen Dank."]
    fake_pipeline.llm.replies = ["Es geht um die Exportfunktion, die seit elf Tagen nicht geht."]

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))
    orch.note_late_barge_in(0)  # nothing heard -> the Turn stays open
    assert orch._reopen_turn is orch.turns[0]
    end_before = orch.turns[0].user_end_ms

    # The fakes run a Turn in microseconds, so the session clock would not move
    # far enough between the two for the defect to be visible. This is the dead
    # time a real cough sits after: the user stopped talking, the persona was
    # cut off, and seconds passed before the microphone fired again.
    monkeypatch.setattr(orch, "_elapsed_ms", lambda: end_before + 9000)

    await collect(orch.run_turn(b"b", "turn.webm", "audio/webm"))

    assert len(orch.turns) == 1, "the reopened Turn is still the only one"
    assert orch.turns[0].user_text == "Erste Haelfte der Frage.", "the phantom added no words"
    assert orch.turns[0].user_end_ms == end_before, "and did not move the utterance's end"
