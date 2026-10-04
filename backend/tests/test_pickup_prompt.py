"""A "Hallo?" into a silent line after the user picked up.

Covers:
  ADR 0110  in an ordinary call the user answers first; if they say nothing,
            the Persona asks whether anybody is there -- twice at most, never
            into speech the client has reported, never in a reverse -- and its
            real opening is still owed to the user's first words
"""

from dataclasses import replace

from shared.turn import Turn
from backend.session.orchestrator import SessionOrchestrator
from backend.session.pickup import PROMPT_AFTER_MS, PickupWatch
from backend.tests.conftest import audio_chunks, collect, completed, states

# pylint: disable=missing-function-docstring

_PROMPTS = ("Hallo?", "Hallo? Hören Sie mich?")


# --- When it is due -------------------------------------------------------


def test_nothing_is_due_before_the_call_is_accepted():
    watch = PickupWatch(_PROMPTS, enabled=True)
    assert watch.delay_ms([], now_ms=10_000, activated=False) is None


def test_the_first_prompt_is_due_a_while_after_the_pick_up():
    watch = PickupWatch(_PROMPTS, enabled=True)
    assert watch.delay_ms([], now_ms=0, activated=True) == PROMPT_AFTER_MS
    assert watch.delay_ms([], now_ms=PROMPT_AFTER_MS + 500, activated=True) == 0


def test_the_second_is_counted_from_the_end_of_the_first():
    watch = PickupWatch(_PROMPTS, enabled=True)
    assert watch.next_line() == "Hallo?"
    said = Turn(seq=1, persona_text="Hallo?", persona_offset_ms=4000, persona_end_ms=4600)

    assert watch.delay_ms([said], now_ms=5000, activated=True) == 4600 + PROMPT_AFTER_MS - 5000


def test_a_user_who_starts_speaking_is_not_talked_over():
    """Their audio arrives only once they finish, so the report of the start is
    all the server has to go on."""
    watch = PickupWatch(_PROMPTS, enabled=True)
    watch.note_speaking(3500)
    assert watch.delay_ms([], now_ms=4000, activated=True) == 3500 + PROMPT_AFTER_MS - 4000


def test_nothing_is_due_once_the_user_has_answered():
    watch = PickupWatch(_PROMPTS, enabled=True)
    answered = Turn(seq=1, user_text="Beispiel GmbH, Müller, guten Tag.")
    assert watch.delay_ms([answered], now_ms=60_000, activated=True) is None


def test_it_asks_twice_and_then_waits():
    watch = PickupWatch(_PROMPTS, enabled=True)
    assert [watch.next_line(), watch.next_line()] == list(_PROMPTS)
    assert watch.delay_ms([], now_ms=60_000, activated=True) is None


def test_a_reverse_never_asks():
    """There the user rang, and the Persona has already picked up."""
    watch = PickupWatch(_PROMPTS, enabled=False)
    assert watch.delay_ms([], now_ms=60_000, activated=True) is None


# --- What is said ---------------------------------------------------------


async def test_the_prompt_is_spoken_as_written_without_a_model_call(persona, scenario, fake_pipeline):
    orch = SessionOrchestrator(persona, scenario)
    orch.start_playback()

    events = await collect(orch.run_pickup_prompt())

    assert not fake_pipeline.llm.calls
    assert audio_chunks(events)
    assert states(events) == ["speaking", "listening"]
    assert completed(events).ends_call is False
    assert orch.turns[0].persona_text == "Hallo?"
    assert orch.turns[0].user_text == ""
    assert orch.history.replies() == ["Hallo?"]


async def test_the_opening_is_still_owed_after_a_prompt(persona, scenario, fake_pipeline):
    """The "Hallo?" is not the Persona's opening: the reply to the user's first
    words still gets the opening instruction, and the greeting in it is not
    mistaken for a re-greeting and regenerated."""
    orch = SessionOrchestrator(persona, scenario)
    orch.start_playback()
    await collect(orch.run_pickup_prompt())
    fake_pipeline.stt.transcripts = ["Oh, Entschuldigung. Beispiel GmbH, Müller, guten Tag."]
    fake_pipeline.llm.replies = ["Guten Tag, hier ist Thomas Brandt. Es geht um meinen Vertrag."]

    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    assert len(fake_pipeline.llm.calls) == 1, "the greeting went out as it was"
    assert "the user has just picked up" in fake_pipeline.llm.calls[0][-1]["content"]
    assert orch.turns[-1].persona_text.startswith("Guten Tag, hier ist Thomas Brandt")
    assert orch.pickup_prompt_delay() is None


async def test_the_second_reply_is_no_longer_an_opening(persona, scenario, fake_pipeline):
    orch = SessionOrchestrator(persona, scenario)
    orch.start_playback()
    await collect(orch.run_pickup_prompt())
    fake_pipeline.stt.transcripts = ["Müller, guten Tag.", "Worum genau?"]
    fake_pipeline.llm.replies = ["Guten Tag, hier ist Thomas Brandt wegen des Vertrags.", "Um die Laufzeit."]

    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))
    await collect(orch.run_turn(b"b", "turn.webm", "audio/webm"))

    assert not any("the user has just picked up" in m["content"] for m in fake_pipeline.llm.calls[1])


def test_a_reverse_orchestrator_schedules_no_prompt(persona, scenario):
    orch = SessionOrchestrator(persona, replace(scenario, reverse=True))
    orch.start_playback()
    assert orch.pickup_prompt_delay() is None


def test_a_prompt_is_recognised_whole_or_cut_off():
    """What a barge-in leaves of one is still not an opening."""
    watch = PickupWatch(_PROMPTS, enabled=True)
    assert watch.is_prompt("Hallo?")
    assert watch.is_prompt("Hallo? Hören")
    assert not watch.is_prompt("Guten Tag, hier ist Thomas Brandt.")
    assert not watch.is_prompt("")
    assert not PickupWatch(_PROMPTS, enabled=False).is_prompt("Hallo?")
