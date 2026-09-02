"""Degenerate-repetition guard and guaranteed closing line.

Covers ADR 0038:
  * a reply that repeats any earlier persona message (not just the
    immediately preceding one -- the model oscillates A-B-A-B), or repeats a
    sentence within itself, is treated as "the model has nothing left to
    say" and ends the call
  * on a backstopped ending (repetition, or an unprompted [CALL_END] that
    was never nudged) a fixed sign-off is synthesised and appended -- taken
    from the Persona's language pack since ADR 0043, because it is spoken
    aloud and so cannot follow the prompt frame into English

  * a reply *most* of which was already in its predecessor -- a fresh opening
    sentence in front of the same block, which the verbatim check never sees
    -- ends the call the same way. This is the gap ADR 0038's own Consequences
    name: a differently-worded repetition of the same content escapes a
    whole-reply check. It is a share of the reply and not a count of
    sentences, so a caller quoting one figure again while moving the call on
    is left alone.
"""

import pytest

from backend.session.language_packs import get_pack
from backend.session.orchestrator import SessionOrchestrator, _has_repeated_sentence
from tests.conftest import audio_chunks, collect, completed, states

FALLBACK_LINE = get_pack("de").fallback_closing_line

# Both fixtures come from real calls. The Persona was reading its whole case
# out per reply, so no two replies were ever verbatim identical and ADR 0038's
# check saw nothing -- while the share carried over separates the two cases
# cleanly: 80% for the restatement, 25% for the reply that moved on.
FACTS = (
    "Das Paket besteht aus 14 Lizenzen fuer 1180 Euro monatlich. "
    "Die Preisanpassung war um 12 Prozent, ohne Aenderung am Leistungsumfang. "
    "Ein Konkurrent hat etwa 800 Euro fuer ein aehnliches Angebot genannt. "
    "Ich will wissen, ob es eine Reduktion gibt, und bis wann."
)
RESTATEMENT = f"Das habe ich Ihnen doch eben schon alles gesagt. {FACTS}"

OPENING = (
    "Guten Tag, hier ist Thomas Brandt, Geschaeftsfuehrer einer mittelstaendischen Firma. "
    "Ich rufe an wegen der Kosten fuer das Insight-Analytics-Paket."
)
ELABORATION = f"{OPENING} {FACTS} Wir denken inzwischen ernsthaft ueber eine Kuendigung nach."

# pylint: disable=missing-function-docstring


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Das ist ein vollstaendiger Satz. Das ist ein vollstaendiger Satz.", True),
        ("Erste Aussage hier zum Thema. Eine voellig andere zweite Aussage.", False),
        ("Ja. Ja. Ja.", False),  # too short to count
        ("Nur ein einziger, ausreichend langer Satz ohne jede Wiederholung.", False),
    ],
)
def test_has_repeated_sentence(text, expected):
    assert _has_repeated_sentence(text) is expected


async def test_reply_repeating_the_previous_reply_ends_the_call(persona, scenario, fake_pipeline):
    line = "Ich brauche dazu bitte eine konkrete Zahl von Ihnen."
    fake_pipeline.stt.transcripts = ["Ich schaue mal nach.", "Einen Moment noch."]
    fake_pipeline.llm.replies = [line, line]  # second turn repeats the first verbatim

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))
    events = await collect(orch.run_turn(b"b", "turn.webm", "audio/webm"))

    tc = completed(events)
    assert tc is not None and tc.ends_call is True
    assert "listening" not in states(events)


async def test_reply_oscillating_back_to_an_earlier_reply_ends_the_call(persona, scenario, fake_pipeline):
    """A-B-A: turn 3 repeats turn 1 with a different reply in between, which a
    "same as the last reply" check would miss."""
    a = "Ich brauche dazu bitte eine konkrete Zahl von Ihnen, sonst kommen wir nicht weiter."
    b = "Also gut, dann warte ich noch einen Moment auf Ihre Rueckmeldung dazu."
    fake_pipeline.stt.transcripts = ["Einen Moment.", "Ich schaue nach.", "Gleich habe ich es."]
    fake_pipeline.llm.replies = [a, b, a]

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_turn(b"1", "turn.webm", "audio/webm"))
    turn2 = await collect(orch.run_turn(b"2", "turn.webm", "audio/webm"))
    assert completed(turn2).ends_call is False, "the B reply in between is not a repeat"
    turn3 = await collect(orch.run_turn(b"3", "turn.webm", "audio/webm"))

    tc = completed(turn3)
    assert tc is not None and tc.ends_call is True
    assert "listening" not in states(turn3)


async def test_short_reply_recurring_non_adjacently_is_not_treated_as_a_loop(
    persona, scenario, fake_pipeline
):
    """A brief acknowledgement can legitimately recur a few Turns apart; only a
    substantial reply coming back counts as the "further back than last" loop.
    (An exact back-to-back repeat is still degenerate at any length --
    `_repeats_last_reply` -- so this spaces the two out.)"""
    short = "Ja, genau."
    fake_pipeline.stt.transcripts = ["Stimmt das so?", "Wirklich?", "Ganz sicher?"]
    fake_pipeline.llm.replies = [short, "Da bin ich mir ziemlich sicher, ja.", short]

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))
    await collect(orch.run_turn(b"b", "turn.webm", "audio/webm"))
    events = await collect(orch.run_turn(b"c", "turn.webm", "audio/webm"))

    assert completed(events).ends_call is False


async def test_backstopped_ending_appends_the_fixed_closing_line(persona, scenario, fake_pipeline):
    """An unprompted [CALL_END] (no farewell from the user) is not trusted to
    contain a goodbye, so the fixed sign-off is synthesised and appended."""
    fake_pipeline.stt.transcripts = ["Gut, dann machen wir das so."]
    fake_pipeline.llm.replies = ["In Ordnung. [CALL_END]"]

    orch = SessionOrchestrator(persona, scenario)
    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    assert completed(events).ends_call is True
    assert FALLBACK_LINE in orch.turns[-1].persona_text
    # the fixed line was actually synthesised, not just appended to text
    assert any(FALLBACK_LINE.encode("utf-8") in c.audio for c in audio_chunks(events))


async def test_nudged_ending_trusts_the_models_own_goodbye(persona, scenario, fake_pipeline):
    """When the user said goodbye, the model was explicitly asked for a
    closing line, so the fixed fallback is NOT appended on top."""
    fake_pipeline.stt.transcripts = ["Auf Wiederhören!"]
    fake_pipeline.llm.replies = ["Danke fuer das Gespraech, auf Wiederhoeren. [CALL_END]"]

    orch = SessionOrchestrator(persona, scenario)
    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    assert completed(events).ends_call is True
    assert FALLBACK_LINE not in orch.turns[-1].persona_text


async def test_a_reply_that_mostly_restates_its_predecessor_ends_the_call(
    persona, scenario, fake_pipeline
):
    """ADR 0038: four of five sentences carried over is the loop the guard is
    for, and it ends the call with the fixed sign-off."""
    fake_pipeline.stt.transcripts = ["Worum geht es denn?", "Welche Module nutzen Sie?"]
    fake_pipeline.llm.replies = [FACTS, RESTATEMENT]

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))
    events = await collect(orch.run_turn(b"b", "turn.webm", "audio/webm"))

    assert completed(events).ends_call is True
    assert FALLBACK_LINE in orch.turns[-1].persona_text
    assert "listening" not in states(events)


async def test_repeating_the_opening_while_moving_on_does_not_end_the_call(
    persona, scenario, fake_pipeline
):
    """The regression a share replaced a sentence count for: asked what he
    wants, the caller repeats his opening and then says several new things.
    That is the right answer to the question, not a loop."""
    fake_pipeline.stt.transcripts = ["Was gibt es denn?", "Und was brauchen Sie von mir?"]
    fake_pipeline.llm.replies = [OPENING, ELABORATION]

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))
    events = await collect(orch.run_turn(b"b", "turn.webm", "audio/webm"))

    assert completed(events).ends_call is False


async def test_a_reply_of_pure_filler_ends_nothing(persona, scenario, fake_pipeline):
    """A reply with no sentence long enough to compare has a share of nothing,
    which must read as "not a restatement" rather than divide by zero. The two
    replies differ, so ADR 0038's verbatim check stays out of the way."""
    fake_pipeline.stt.transcripts = ["Passt das so?", "Und sonst?"]
    fake_pipeline.llm.replies = ["Ja, genau.", "Aha, verstehe."]

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))
    events = await collect(orch.run_turn(b"b", "turn.webm", "audio/webm"))

    assert completed(events).ends_call is False


async def test_a_shared_short_sentence_is_not_a_restatement(persona, scenario, fake_pipeline):
    """ADR 0038: below the length threshold a shared sentence is filler, not
    the same content, and must not count against the call."""
    fake_pipeline.stt.transcripts = ["Und wann gilt der?", "Ab naechstem Monat."]
    fake_pipeline.llm.replies = [
        "Ja, genau. Ab wann genau wuerde der neue Preis denn gelten?",
        "Ja, genau. Dann halten wir das so fest und ich pruefe es intern.",
    ]

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))
    events = await collect(orch.run_turn(b"b", "turn.webm", "audio/webm"))

    assert completed(events).ends_call is False
