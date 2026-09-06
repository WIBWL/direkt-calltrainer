"""The caller's notes and the history window (ADR 0071).

Past a handful of exchanges the 4B model misread the raw transcript -- it
attributed its own case to the user and asked about it for eight Turns. So
the model no longer reads the whole history: it reads the system prompt, its
notes on the call (one background summarisation call per completed exchange,
never on the path to a reply), and the last few exchanges verbatim. The full
history is still kept: the repetition guards, the barge-in trims and the
Transcript work on it, not on the model's view.
"""

from backend.session.models import TurnCompleted
from backend.session.nudges import STATE_NOTES_FRAME
from backend.session.orchestrator import HISTORY_WINDOW, SessionOrchestrator
from tests.conftest import collect

# pylint: disable=missing-function-docstring,protected-access

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
        await orch.flush_state()
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
    assert USER[0] in [m["content"] for m in orch._messages], "but the full record keeps it"


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
    if scenario.success_condition:
        assert scenario.success_condition in prompt[0]["content"]


async def test_a_failed_refresh_keeps_the_previous_notes(persona, scenario, fake_pipeline):
    fake_pipeline.llm.states = ["- first notes"]
    fake_pipeline.llm.state_fail_times = 0
    orch = SessionOrchestrator(persona, scenario)
    await _run(orch, fake_pipeline, 1)
    assert orch._state == "- first notes"

    fake_pipeline.llm.state_fail_times = 1
    fake_pipeline.stt.transcripts = [USER[1]]
    fake_pipeline.llm.replies = [PERSONA[1]]
    await collect(orch.run_turn(b"b", "turn.webm", "audio/webm"))
    await orch.flush_state()

    assert orch._state == "- first notes", "stale notes beat none; the call goes on"


async def test_a_barge_in_re_refreshes_the_notes_with_only_the_heard_part(
    persona, scenario, fake_pipeline, monkeypatch
):
    monkeypatch.setattr("backend.session.orchestrator.tts.duration_ms", lambda _wav: 10000)
    orch = SessionOrchestrator(persona, scenario)
    await _run(orch, fake_pipeline, 1)
    full = PERSONA[0]

    orch.note_late_barge_in(2000)  # a few words in
    await orch.flush_state()

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
