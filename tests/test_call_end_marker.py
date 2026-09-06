"""[CALL_END] marker handling and foreign-script scrubbing.

Covers ADR 0033 (streamed pipeline): the persona ends a call by emitting a
[CALL_END] marker in its text stream. The marker must never be spoken or
stored, and stray non-Latin script from the small model must be dropped
before synthesis.
"""

import pytest

from backend.session.orchestrator import (
    SessionOrchestrator,
    _ReplyProgress,
    _strip_end_marker,
    _strip_foreign_script,
)
from tests.conftest import collect, completed

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
    """The chunker flushes at sentence ends, so a marker mid-chunk drags the
    model's next sentence along -- it was being read out after the goodbye."""
    progress = _ReplyProgress()
    cleaned = _strip_end_marker("Danke, auf Wiederhören. [CALL_END] Ich bin Thomas Brandt.", progress)
    assert cleaned == "Danke, auf Wiederhören."
    assert progress.ends_call is True


# --- An unprompted marker on a reply that is still pressing (ADR 0037) ------
# The model ended a live call with "[CALL_END]" straight after "Ich will
# wissen, was los ist und wann ..." -- no goodbye, the demand still open. The
# marker is the model's own idea on such a Turn, and is vetoed.


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
    """A farewell in the last sentence wins, whatever else it carries."""
    fake_pipeline.stt.transcripts = ["Ich melde mich morgen mit einem Termin."]
    fake_pipeline.llm.replies = [
        "Gut, dann brauche ich nichts weiter, ich warte auf Ihren Anruf, auf Wiederhören. [CALL_END]"
    ]

    orch = SessionOrchestrator(persona, scenario)
    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    assert completed(events).ends_call is True


async def test_a_goodbye_followed_by_a_trailing_question_still_ends_the_call(persona, scenario, fake_pipeline):
    """docs/research/model-parameters.md: half the legitimate endings finish
    on a question after the goodbye. The farewell decides, wherever it sits."""
    fake_pipeline.stt.transcripts = ["Ich melde mich morgen mit einem Termin."]
    fake_pipeline.llm.replies = ["Danke, auf Wiederhören. Darf ich mich morgen bei Ihnen melden? [CALL_END]"]

    orch = SessionOrchestrator(persona, scenario)
    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    assert completed(events).ends_call is True


async def test_a_nudged_marker_is_taken_at_its_word(persona, scenario, fake_pipeline):
    """After the user said goodbye the closing nudge asked for the marker; a
    persona that ends on a grumble then still ends (ADR 0037)."""
    fake_pipeline.stt.transcripts = ["Okay, tschüss dann!"]
    fake_pipeline.llm.replies = ["Ich will trotzdem wissen, wann das behoben wird. [CALL_END]"]

    orch = SessionOrchestrator(persona, scenario)
    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    assert completed(events).ends_call is True


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
