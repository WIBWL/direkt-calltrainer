"""[CALL_END] is never spoken or stored; stray foreign script is dropped (ADR 0033)."""

import pytest

from backend.session.events import AudioChunk
from backend.session.orchestrator import (
    SessionOrchestrator,
    _ReplyProgress,
    _strip_end_marker,
    _strip_foreign_script,
)
from backend.tests.conftest import collect, completed, failure

# pylint: disable=missing-function-docstring


@pytest.mark.parametrize(
    "raw",
    ["Danke, auf Wiederhören. [CALL_END]", "Bis bald.[CALL_END]", "Tschüss. [call_end]", "Ende [ CALL END ]"],
)
def test_marker_is_detected_and_removed(raw):
    progress = _ReplyProgress()
    cleaned = _strip_end_marker(raw, progress)
    assert progress.ends_call is True
    assert "call" not in cleaned.lower()
    assert "[" not in cleaned


def test_text_without_marker_is_untouched():
    progress = _ReplyProgress()
    text = "Und wie sieht es mit der Laufzeit aus?"
    assert _strip_end_marker(text, progress) == text
    assert progress.ends_call is False


def test_text_after_the_marker_goes_with_it():
    progress = _ReplyProgress()
    cleaned = _strip_end_marker("Danke, auf Wiederhören. [CALL_END] Ich bin Thomas Brandt.", progress)
    assert cleaned == "Danke, auf Wiederhören."
    assert progress.ends_call is True


# Seen live: an unprompted [CALL_END] straight after an open demand is vetoed.


async def test_an_unprompted_marker_on_a_demand_is_ignored(persona, scenario, fake_pipeline):
    fake_pipeline.stt.transcripts = ["Da kann ich gerade nichts versprechen."]
    fake_pipeline.llm.replies = [
        "Das Ticket ist seit elf Tagen offen. Ich will wissen, wann das behoben wird. [CALL_END]"
    ]

    orch = SessionOrchestrator(persona, scenario)
    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    assert completed(events).ends_call is False
    assert orch.turns[0].persona_text == "Das Ticket ist seit elf Tagen offen. Ich will wissen, wann das behoben wird."
    assert "Wiederhören" not in orch.turns[0].persona_text, "no fallback goodbye either"


async def test_an_unprompted_marker_on_an_open_question_is_ignored(persona, scenario, fake_pipeline):
    fake_pipeline.stt.transcripts = ["Ich schaue nach."]
    fake_pipeline.llm.replies = ["Können Sie mir dann wenigstens einen Termin nennen? [CALL_END]"]

    orch = SessionOrchestrator(persona, scenario)
    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    assert completed(events).ends_call is False


async def test_an_unprompted_marker_with_a_goodbye_still_ends_the_call(persona, scenario, fake_pipeline):
    fake_pipeline.stt.transcripts = ["Ich melde mich morgen mit einem Termin."]
    fake_pipeline.llm.replies = [
        "Gut, dann brauche ich nichts weiter, ich warte auf Ihren Anruf, auf Wiederhören. [CALL_END]"
    ]

    orch = SessionOrchestrator(persona, scenario)
    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    assert completed(events).ends_call is True


async def test_a_goodbye_followed_by_a_trailing_question_still_ends_the_call(persona, scenario, fake_pipeline):
    fake_pipeline.stt.transcripts = ["Ich melde mich morgen mit einem Termin."]
    fake_pipeline.llm.replies = ["Danke, auf Wiederhören. Darf ich mich morgen bei Ihnen melden? [CALL_END]"]

    orch = SessionOrchestrator(persona, scenario)
    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    assert completed(events).ends_call is True


async def test_a_goodbye_without_the_marker_still_ends_the_call(persona, scenario, fake_pipeline):
    fake_pipeline.stt.transcripts = ["Bis 16:30 Uhr läuft der Export wieder."]
    fake_pipeline.llm.replies = [
        "Eine Bestätigung allein reicht nicht, wenn die Daten dann nicht fließen. "
        "Sollte es weiter haken, müssen wir eskalieren. Ich danke Ihnen. Auf Wiederhören."
    ]

    orch = SessionOrchestrator(persona, scenario)
    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    assert completed(events).ends_call is True
    spoken = " ".join(text for text, _voice, _language in fake_pipeline.tts.calls)
    assert spoken.count("Wiederhören") == 1, "its own goodbye, not the fallback line on top of it"


async def test_a_reply_that_only_presses_does_not_end_the_call(persona, scenario, fake_pipeline):
    fake_pipeline.stt.transcripts = ["Ich schaue mir das Ticket an."]
    fake_pipeline.llm.replies = [
        "Ich danke Ihnen für die Rückmeldung. Wann genau kann ich mit einer Lösung rechnen?"
    ]

    orch = SessionOrchestrator(persona, scenario)
    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    assert completed(events).ends_call is False


async def test_a_nudged_marker_is_taken_at_its_word(persona, scenario, fake_pipeline):
    fake_pipeline.stt.transcripts = ["Okay, tschüss dann!"]
    fake_pipeline.llm.replies = ["Ich will trotzdem wissen, wann das behoben wird. [CALL_END]"]

    orch = SessionOrchestrator(persona, scenario)
    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    assert completed(events).ends_call is True


@pytest.mark.parametrize(
    "reply",
    ["[CALL_END]", "[CALL_END] Auf Wiederhören.", "   [CALL_END]  "],
)
async def test_a_reply_that_is_only_the_marker_ends_the_call(
    persona, scenario, fake_pipeline, reply
):
    fake_pipeline.stt.transcripts = ["Okay, tschüss dann!"]
    fake_pipeline.llm.replies = [reply]

    orch = SessionOrchestrator(persona, scenario)
    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    assert failure(events) is None, "a hang-up is not a pipeline failure"
    assert completed(events).ends_call is True
    assert orch.ended is True
    assert len(fake_pipeline.llm.calls) == 1, "and no retry was spent on it"


async def test_an_ending_with_no_words_still_says_goodbye(persona, scenario, fake_pipeline):
    fake_pipeline.stt.transcripts = ["Okay, tschüss dann!"]
    fake_pipeline.llm.replies = ["[CALL_END]"]

    orch = SessionOrchestrator(persona, scenario)
    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    assert any(isinstance(e, AudioChunk) for e in events), "something was spoken"
    assert orch.turns[0].persona_text, "and it is in the Transcript"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Guten Tag 你好 zusammen", "Guten Tag  zusammen"),
        ("Alles klar。", "Alles klar"),
        ("こんにちは", ""),
        ("Nur deutscher Text.", "Nur deutscher Text."),
    ],
)
def test_foreign_script_is_scrubbed(raw, expected):
    assert _strip_foreign_script(raw) == expected
