"""The caller's notes and the history window (ADR 0071, ADR 0075, ADR 0103).

The 4B model misread long raw transcripts, so it reads the system prompt, its
notes (one background summarisation per exchange) and the last few exchanges.
The full history is still kept for the guards, the trims and the Transcript."""

from backend.session.models import TurnCompleted
from backend.session.nudges import STATE_NOTES_FRAME
from backend.session.orchestrator import HISTORY_WINDOW, SessionOrchestrator
from tests.conftest import collect

# pylint: disable=missing-function-docstring

USER = [
    "Worum geht es denn genau?",
    "Ich schaue mir das Ticket gerade an.",
    "Der Kollege meldet sich morgen bei Ihnen.",
    "Ich kann Ihnen einen Termin am Freitag anbieten.",
    "Passt das so fuer Sie?",
]
PERSONA = [
    "Es geht um die Exportfunktion, die seit elf Tagen nicht funktioniert.",
    "Das Ticket ist seit elf Tagen offen, ich brauche einen konkreten Termin.",
    "Morgen reicht mir nicht, ich will wissen, wann der Export wieder geht.",
    "Freitag klingt gut, koennen Sie mir das bitte schriftlich bestaetigen?",
    "Ja, das passt, danke Ihnen.",
]


async def _run(orch, fake_pipeline, turns):
    fake_pipeline.stt.transcripts = USER[:turns]
    fake_pipeline.llm.replies = PERSONA[:turns]
    events = []
    for i in range(turns):
        events = await collect(orch.run_turn(bytes([i]), "turn.webm", "audio/webm"))
        await orch.notes.settle()
    return events


async def test_the_model_reads_notes_plus_a_window_not_the_whole_history(persona, scenario, fake_pipeline):
    fake_pipeline.llm.states = [f"- notes after exchange {i}" for i in range(1, 6)]
    orch = SessionOrchestrator(persona, scenario)
    await _run(orch, fake_pipeline, 5)

    view = fake_pipeline.llm.calls[-1]
    assert view[0]["role"] == "system", "the system prompt first"
    assert view[1]["role"] == "system" and view[1]["content"].startswith(STATE_NOTES_FRAME)
    assert "notes after exchange 4" in view[1]["content"], "the notes of every exchange before this Turn"
    history = [m for m in view[2:] if m["role"] in ("user", "assistant")]
    assert len(history) == HISTORY_WINDOW, "the last three exchanges verbatim"
    assert USER[0] not in str(view), "the first exchange reaches the model only through the notes"
    assert USER[0] in [m["content"] for m in orch.history.messages], "but the full record keeps it"


async def test_no_notes_before_the_first_exchange_has_completed(persona, scenario, fake_pipeline):
    fake_pipeline.llm.states = ["- would not be read yet"]
    orch = SessionOrchestrator(persona, scenario)
    await _run(orch, fake_pipeline, 1)

    assert not any(m["content"].startswith(STATE_NOTES_FRAME) for m in fake_pipeline.llm.calls[0])
    assert len(fake_pipeline.llm.state_calls) == 1, "the refresh runs once the exchange is complete"


async def test_the_refresh_gets_the_exchange_and_the_condition_to_weigh_it_against(persona, scenario, fake_pipeline):
    orch = SessionOrchestrator(persona, scenario)
    await _run(orch, fake_pipeline, 1)

    prompt = fake_pipeline.llm.state_calls[-1]
    assert USER[0] in prompt[-1]["content"] and PERSONA[0] in prompt[-1]["content"]
    assert persona.name in prompt[0]["content"]
    if scenario.call_goal:
        assert scenario.call_goal in prompt[0]["content"]


async def test_a_failed_refresh_keeps_the_previous_notes(persona, scenario, fake_pipeline):
    fake_pipeline.llm.states = ["- first notes"]
    fake_pipeline.llm.state_fail_times = 0
    orch = SessionOrchestrator(persona, scenario)
    await _run(orch, fake_pipeline, 1)
    assert orch.notes.text == "- first notes"

    fake_pipeline.llm.state_fail_times = 1
    fake_pipeline.stt.transcripts = [USER[1]]
    fake_pipeline.llm.replies = [PERSONA[1]]
    await collect(orch.run_turn(b"b", "turn.webm", "audio/webm"))
    await orch.notes.settle()

    assert orch.notes.text == "- first notes", "stale notes beat none; the call goes on"


async def test_a_barge_in_re_refreshes_the_notes_with_only_the_heard_part(
    persona, scenario, fake_pipeline, monkeypatch
):
    monkeypatch.setattr("backend.session.orchestrator.tts.duration_ms", lambda _wav: 10000)
    orch = SessionOrchestrator(persona, scenario)
    await _run(orch, fake_pipeline, 1)
    full = PERSONA[0]

    orch.note_late_barge_in(2000)  # a few words in
    await orch.notes.settle()

    heard = orch.turns[0].persona_text
    assert full.startswith(heard) and heard != full
    latest = fake_pipeline.llm.state_calls[-1][-1]["content"]
    assert f"Caller: {heard}" in latest
    assert full not in latest, "the unheard part never reaches the notes"


async def test_the_guards_still_see_the_whole_history(persona, scenario, fake_pipeline):
    """A verbatim repeat of a line from four exchanges back -- outside the
    window -- is still caught before it is spoken (ADR 0038 on the full
    record), regenerated, and ends the call when the regeneration loops too."""
    fake_pipeline.llm.states = [f"- notes {i}" for i in range(1, 8)]
    orch = SessionOrchestrator(persona, scenario)
    await _run(orch, fake_pipeline, 4)

    fake_pipeline.stt.transcripts = [USER[4]]
    fake_pipeline.llm.replies = [PERSONA[0], PERSONA[0]]  # the loop, and the regeneration looping again
    events = await collect(orch.run_turn(b"z", "turn.webm", "audio/webm"))

    assert any(isinstance(e, TurnCompleted) and e.ends_call for e in events)
    assert PERSONA[0] not in str(fake_pipeline.llm.calls[-2][2:]), "it was outside the window"


def _summarising_llm(monkeypatch, fake_pipeline):
    """A summariser that carries forward everything it is handed, like a real one.

    The canned `states` never contain the Persona's words, so with them the
    "unheard part stays out" assertions would hold however the notes were built.
    """
    async def summarise(messages, **_kwargs):
        fake_pipeline.llm.state_calls.append(messages)
        return "\n".join(m["content"] for m in messages)

    monkeypatch.setattr("backend.clients.llm.complete", summarise)


async def test_a_trimmed_reply_is_summarised_from_the_notes_that_predate_it(
    persona, scenario, fake_pipeline, monkeypatch
):
    """A re-refresh after a barge-in starts from the notes as they stood *before*.

    Notes are rewritten from the previous notes (ADR 0075), so the first refresh may
    already hold the unheard sentence; ADR 0071's "never record unheard words" holds
    only if the second pass starts from before them."""
    monkeypatch.setattr("backend.session.orchestrator.tts.duration_ms", lambda _wav: 10000)
    _summarising_llm(monkeypatch, fake_pipeline)

    orch = SessionOrchestrator(persona, scenario)
    await _run(orch, fake_pipeline, 1)
    full = PERSONA[0]
    assert full in orch.notes.text, "the notes absorbed the whole reply before the barge-in"

    orch.note_late_barge_in(2000)  # a few words in
    await orch.notes.settle()

    heard = orch.turns[0].persona_text
    assert full.startswith(heard) and heard != full
    unheard = full[len(heard):].strip()
    assert unheard and unheard not in orch.notes.text, "the unheard tail is out of the notes"
    assert heard in orch.notes.text, "and what was heard is in them"


async def test_a_reply_nobody_heard_leaves_the_notes_as_they_were(
    persona, scenario, fake_pipeline, monkeypatch
):
    """A reply dropped whole by a barge-in: the notes revert to before the exchange.

    The refresh for it was already in flight with the full reply; left alone it wrote
    the Persona's unheard words into the notes and nothing later replaced them.
    """
    monkeypatch.setattr("backend.session.orchestrator.tts.duration_ms", lambda _wav: 10000)
    _summarising_llm(monkeypatch, fake_pipeline)

    orch = SessionOrchestrator(persona, scenario)
    await _run(orch, fake_pipeline, 2)
    before = orch.notes.text
    assert PERSONA[1] in before

    fake_pipeline.stt.transcripts = [USER[2]]
    fake_pipeline.llm.replies = [PERSONA[2]]
    await collect(orch.run_turn(b"c", "turn.webm", "audio/webm"))
    orch.note_late_barge_in(0)  # nothing played at all
    await orch.notes.settle()

    assert orch.turns[-1].persona_text == "", "the reply was dropped"
    assert PERSONA[2] not in orch.notes.text, "and it is not in the notes either"
    assert orch.notes.text == before, "which are exactly the notes from before it"
