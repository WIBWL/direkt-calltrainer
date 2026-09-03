"""Degenerate-repetition guard, re-introduction regeneration, and the
guaranteed closing line.

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

  * a reply that *opens* by greeting or re-introducing after the call is
    under way is caught on its first chunk, before any audio, and the model
    is re-asked once with an explicit nudge -- the call carries on rather
    than ending, because the reply was never spoken.
"""

import pytest

from backend.session.language_packs import get_pack
from backend.session.orchestrator import SessionOrchestrator, _asks_to_repeat, _has_repeated_sentence
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
# Expands on the opening -- repeats its subject and one figure -- but does not
# greet or name himself again, so the re-introduction guard leaves it alone.
ELABORATION = (
    "Es geht mir um die Kosten fuer das Insight-Analytics-Paket. "
    f"{FACTS} Wir denken inzwischen ernsthaft ueber eine Kuendigung nach."
)

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


async def test_expanding_on_the_opening_without_re_greeting_does_not_end_the_call(
    persona, scenario, fake_pipeline
):
    """The regression a share replaced a sentence count for: asked what he
    wants, the caller restates his subject and one figure and then says
    several new things. That is the right answer to the question, not a loop,
    and -- because he does not greet or name himself again -- not a
    re-introduction either."""
    fake_pipeline.stt.transcripts = ["Was gibt es denn?", "Und was brauchen Sie von mir?"]
    fake_pipeline.llm.replies = [OPENING, ELABORATION]

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))
    events = await collect(orch.run_turn(b"b", "turn.webm", "audio/webm"))

    assert completed(events).ends_call is False
    # spoken as-is, not regenerated away
    assert orch.turns[-1].persona_text == ELABORATION
    assert len(fake_pipeline.llm.calls) == 2


async def test_a_reply_that_opens_by_greeting_again_is_regenerated(persona, scenario, fake_pipeline):
    """ADR 0038: the persona restarting the call from the top -- greeting
    again, name again -- is caught on the first chunk and the model is
    re-asked, before any of that greeting is synthesised."""
    regreet = "Guten Tag, hier ist Thomas Brandt. Es geht um unseren Vertrag und die Kosten."
    clean = "Die laufenden Kosten sind zu hoch, wir zahlen jeden Monat deutlich zu viel."
    fake_pipeline.stt.transcripts = ["Guten Tag, wie kann ich helfen?"]
    fake_pipeline.llm.replies = [
        "Guten Tag, ich bin Thomas Brandt. Ich habe eine Frage zu unserem Vertrag.",  # opening
        regreet,                                                                     # -> regenerate
        clean,                                                                       # the retry
    ]

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_opening_turn())
    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    spoken = b"".join(c.audio for c in audio_chunks(events))
    assert b"hier ist Thomas Brandt" not in spoken  # the re-greeting never went out
    assert clean.encode("utf-8") in spoken
    assert orch.turns[-1].persona_text == clean
    assert orch._messages[-1] == {"role": "assistant", "content": clean}  # pylint: disable=protected-access
    assert len(fake_pipeline.llm.calls) == 3
    assert completed(events).ends_call is False


async def test_the_regeneration_nudge_quotes_the_rejected_opening(persona, scenario, fake_pipeline):
    """The retry is given the greeting it must steer away from, verbatim."""
    fake_pipeline.stt.transcripts = ["Guten Tag."]
    fake_pipeline.llm.replies = [
        "Guten Tag, ich bin Thomas Brandt. Es geht um den Vertrag.",   # opening
        "Guten Tag, Thomas Brandt hier. Der Vertrag laeuft schlecht.",  # -> regenerate
        "Der Vertrag laeuft aus dem Ruder, das muss sich aendern.",     # retry
    ]

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_opening_turn())
    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    retry_messages = fake_pipeline.llm.calls[-1]
    assert any(
        m["role"] == "system" and "Guten Tag, Thomas Brandt hier." in m["content"]
        for m in retry_messages
    )


async def test_a_normal_turn_carries_a_nudge_quoting_the_previous_reply(persona, scenario, fake_pipeline):
    """ADR 0038: every turn past the opening reminds the model of its own last
    reply, so a reworded repeat is discouraged before it is generated."""
    fake_pipeline.stt.transcripts = ["Und wie stellen Sie sich das vor?"]
    fake_pipeline.llm.replies = [
        "Ich moechte eine konkrete Zusage zum Preis, keine allgemeine Auskunft.",  # opening
        "Also, konkret waere mir eine feste Zahl bis Freitag wichtig.",
    ]

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_opening_turn())
    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    sent = fake_pipeline.llm.calls[-1]
    assert any(
        m["role"] == "system" and "konkrete Zusage zum Preis" in m["content"]
        for m in sent
    )


@pytest.mark.parametrize(
    "text,pack_id,expected",
    [
        ("Verzeihung, wer sind Sie nochmals? Das habe ich nicht verstanden.", "de", True),
        ("Wie war Ihr Name?", "de", True),
        ("Können Sie das bitte wiederholen?", "de", True),
        ("Sagen Sie das nochmal, bitte.", "de", True),
        ("Wie bitte?", "de", True),
        ("Ich schaue da nochmal in unser System.", "de", False),
        ("Warum kostet das so viel?", "de", False),
        ("Sorry, who are you again?", "en", True),
        ("Could you repeat that?", "en", True),
        ("I didn't catch that.", "en", True),
        ("Let me check once more on my side.", "en", False),
    ],
)
def test_asks_to_repeat_recognises_requests_for_a_repeat(text, pack_id, expected):
    assert _asks_to_repeat(text, get_pack(pack_id)) is expected


async def test_a_repeat_the_user_asked_for_does_not_end_the_call(persona, scenario, fake_pipeline):
    """ADR 0038: 'wer sind Sie nochmal?' makes repeating the introduction the
    right answer — the re-introduction guard, the verbatim check and the
    restatement check all stand down for the immediately previous reply, and
    the call carries on."""
    intro = "Guten Tag, ich bin Thomas Brandt aus der Geschaeftsleitung. Es geht um den Vertrag."
    fake_pipeline.stt.transcripts = ["Verzeihung, wer sind Sie nochmal? Das habe ich nicht verstanden."]
    fake_pipeline.llm.replies = [intro, intro]  # opening, then the same again on request

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_opening_turn())
    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    assert completed(events).ends_call is False
    assert "listening" in states(events)
    assert b"Thomas Brandt" in b"".join(c.audio for c in audio_chunks(events))  # re-introduced, not suppressed
    assert len(fake_pipeline.llm.calls) == 2  # not regenerated


async def test_a_requested_repeat_swaps_the_anti_repeat_nudge_for_a_clarify_nudge(
    persona, scenario, fake_pipeline
):
    """The standing 'say something different' reminder would fight the user's
    request; it is replaced by 'say it again, reworded shorter'."""
    fake_pipeline.stt.transcripts = ["Wie war Ihr Name nochmal?"]
    fake_pipeline.llm.replies = ["Mein Name ist Thomas Brandt.", "Thomas Brandt, gerne nochmal."]

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_opening_turn())
    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    systems = [m["content"] for m in fake_pipeline.llm.calls[-1] if m["role"] == "system"]
    assert not any("previous reply in this call" in s for s in systems)
    assert any("did not catch your previous reply" in s for s in systems)


async def test_asking_again_after_a_rephrase_gets_a_firmer_nudge(persona, scenario, fake_pipeline):
    """A third rendering of the same content does not help — the persona is
    told to ask what is unclear or move on."""
    fake_pipeline.stt.transcripts = [
        "Was haben Sie gesagt? Nicht verstanden.",
        "Nochmal bitte, ich hab es wieder nicht mitbekommen.",
    ]
    fake_pipeline.llm.replies = [
        "Der Preis ist zu hoch, wir zahlen jeden Monat achtzehnhundert Euro dafuer.",  # opening
        "Der Preis ist zu hoch, monatlich achtzehnhundert Euro.",
        "Achtzehnhundert Euro im Monat, das ist zu viel.",
    ]

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_opening_turn())
    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))
    await collect(orch.run_turn(b"b", "turn.webm", "audio/webm"))

    systems = [m["content"] for m in fake_pipeline.llm.calls[-1] if m["role"] == "system"]
    assert any("Ask which part is unclear" in s for s in systems)


async def test_re_dumping_an_older_reply_ends_the_call_even_when_a_repeat_was_asked(
    persona, scenario, fake_pipeline
):
    """The exemption covers the *immediately previous* reply only: parroting one
    from further back verbatim is still the loop the guard is for."""
    a = "Ich brauche eine feste Zusage zum Preis, bitte eine konkrete Zahl mit Datum."
    b = "Also gut, dann warte ich noch kurz auf Ihre Rueckmeldung dazu."
    fake_pipeline.stt.transcripts = [
        "Worum ging es?",
        "Und was war Ihr Anliegen?",
        "Sorry, was haben Sie da gesagt? Nicht verstanden.",
    ]
    fake_pipeline.llm.replies = [a, b, a]  # turn 3 re-dumps turn 1 verbatim

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_turn(b"1", "turn.webm", "audio/webm"))
    await collect(orch.run_turn(b"2", "turn.webm", "audio/webm"))
    events = await collect(orch.run_turn(b"3", "turn.webm", "audio/webm"))

    assert completed(events).ends_call is True


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
