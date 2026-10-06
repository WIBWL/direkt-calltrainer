"""Repetition guards, regeneration and the guaranteed closing line (ADR 0038)."""

import pytest

from shared.language_packs import get_pack
from backend.session.events import Failed
from backend.session.orchestrator import SessionOrchestrator, _asks_to_repeat
from backend.session.repetition import has_repeated_sentence as _has_repeated_sentence
from backend.session.repetition import drop_said_sentences, long_sentences, restates, strip_echoed_prefix
from backend.tests.conftest import audio_chunks, collect, completed, states

FALLBACK_LINE = get_pack("de").fallback_closing_line

# From real calls: no two replies were verbatim equal, but the share carried over
# separates them (80 % restatement, 25 % moved on).
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


_FACT = "Wir wurden im März doppelt belastet, einmal am dritten und einmal am siebzehnten."
_AMOUNT = "Der Betrag lag bei vierhundertachtzig Euro pro Abbuchung."
_DEADLINE = "Ich erwarte, dass Sie das bis Ende der Woche korrigieren."


@pytest.mark.parametrize(
    "previous, reply",
    [
        # A share of one sentence is no share: repeating a figure on request is normal.
        (f"{_FACT} {_AMOUNT} {_DEADLINE}", f"Ganz genau. {_AMOUNT}"),
        (f"{_FACT} {_AMOUNT} {_DEADLINE}", _FACT),
    ],
)
def test_a_single_carried_sentence_is_not_a_restatement(previous, reply):
    assert restates(reply, previous) is False


def test_a_reply_that_is_mostly_its_predecessor_still_ends_the_call():
    assert restates(f"{_FACT} {_AMOUNT}", f"{_FACT} {_AMOUNT} {_DEADLINE}") is True


async def test_reply_repeating_the_previous_reply_ends_the_call(persona, scenario, fake_pipeline):
    line = "Ich brauche dazu bitte eine konkrete Zahl von Ihnen."
    fake_pipeline.stt.transcripts = ["Ich schaue mal nach.", "Einen Moment noch."]
    # The second turn repeats the first and is re-asked; the third is the
    # regeneration looping, which is spoken and ends the call.
    fake_pipeline.llm.replies = [line, line, line]

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))
    events = await collect(orch.run_turn(b"b", "turn.webm", "audio/webm"))

    tc = completed(events)
    assert tc is not None and tc.ends_call is True
    assert "listening" not in states(events)
    assert len(fake_pipeline.llm.calls) == 3, "one regeneration, then the backstop"


async def test_reply_oscillating_back_to_an_earlier_reply_ends_the_call(persona, scenario, fake_pipeline):
    a = "Ich brauche dazu bitte eine konkrete Zahl von Ihnen, sonst kommen wir nicht weiter."
    b = "Also gut, dann warte ich noch einen Moment auf Ihre Rueckmeldung dazu."
    fake_pipeline.stt.transcripts = ["Einen Moment.", "Ich schaue nach.", "Gleich habe ich es."]
    fake_pipeline.llm.replies = [a, b, a, a]  # the last `a`: the regeneration looping again

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
    short = "Ja, genau."
    fake_pipeline.stt.transcripts = ["Stimmt das so?", "Wirklich?", "Ganz sicher?"]
    fake_pipeline.llm.replies = [short, "Da bin ich mir ziemlich sicher, ja.", short]

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))
    await collect(orch.run_turn(b"b", "turn.webm", "audio/webm"))
    events = await collect(orch.run_turn(b"c", "turn.webm", "audio/webm"))

    assert completed(events).ends_call is False


async def test_backstopped_ending_appends_the_fixed_closing_line(persona, scenario, fake_pipeline):
    fake_pipeline.stt.transcripts = ["Gut, dann machen wir das so."]
    fake_pipeline.llm.replies = ["In Ordnung. [CALL_END]"]

    orch = SessionOrchestrator(persona, scenario)
    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    assert completed(events).ends_call is True
    assert FALLBACK_LINE in orch.turns[-1].persona_text
    # the fixed line was actually synthesised, not just appended to text
    assert any(FALLBACK_LINE.encode("utf-8") in c.audio for c in audio_chunks(events))


async def test_nudged_ending_trusts_the_models_own_goodbye(persona, scenario, fake_pipeline):
    fake_pipeline.stt.transcripts = ["Auf Wiederhören!"]
    fake_pipeline.llm.replies = ["Danke fuer das Gespraech, auf Wiederhoeren. [CALL_END]"]

    orch = SessionOrchestrator(persona, scenario)
    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    assert completed(events).ends_call is True
    assert FALLBACK_LINE not in orch.turns[-1].persona_text


async def test_a_reply_that_mostly_restates_its_predecessor_is_trimmed_to_what_is_new(
    persona, scenario, fake_pipeline
):
    fake_pipeline.stt.transcripts = ["Worum geht es denn?", "Welche Module nutzen Sie?"]
    fake_pipeline.llm.replies = [FACTS, RESTATEMENT]
    carried = set(long_sentences(FACTS))
    fresh = [s for s in long_sentences(RESTATEMENT) if s not in carried]
    assert len(fresh) == 1, "the fixture: one new sentence among the carried ones"

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))
    events = await collect(orch.run_turn(b"b", "turn.webm", "audio/webm"))

    assert completed(events).ends_call is False
    spoken = orch.turns[-1].persona_text
    assert FALLBACK_LINE not in spoken
    assert fresh[0] in spoken.lower(), "the new sentence is spoken"
    assert not any(old in spoken.lower() for old in carried), "the carried ones are not"
    assert "listening" in states(events)


async def test_expanding_on_the_opening_without_re_greeting_does_not_end_the_call(
    persona, scenario, fake_pipeline
):
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
    assert orch.history.messages[-1] == {"role": "assistant", "content": clean}
    assert len(fake_pipeline.llm.calls) == 3
    assert completed(events).ends_call is False


async def test_the_regeneration_nudge_quotes_the_rejected_opening(persona, scenario, fake_pipeline):
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
    fake_pipeline.stt.transcripts = ["Wie war Ihr Name nochmal?"]
    fake_pipeline.llm.replies = ["Mein Name ist Thomas Brandt.", "Thomas Brandt, gerne nochmal."]

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_opening_turn())
    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    systems = [m["content"] for m in fake_pipeline.llm.calls[-1] if m["role"] == "system"]
    assert not any("previous reply in this call" in s for s in systems)
    assert any("did not catch your previous reply" in s for s in systems)


async def test_asking_again_after_a_rephrase_gets_a_firmer_nudge(persona, scenario, fake_pipeline):
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
    fake_pipeline.stt.transcripts = ["Passt das so?", "Und sonst?"]
    fake_pipeline.llm.replies = ["Ja, genau.", "Aha, verstehe."]

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))
    events = await collect(orch.run_turn(b"b", "turn.webm", "audio/webm"))

    assert completed(events).ends_call is False


async def test_a_shared_short_sentence_is_not_a_restatement(persona, scenario, fake_pipeline):
    fake_pipeline.stt.transcripts = ["Und wann gilt der?", "Ab naechstem Monat."]
    fake_pipeline.llm.replies = [
        "Ja, genau. Ab wann genau wuerde der neue Preis denn gelten?",
        "Ja, genau. Dann halten wir das so fest und ich pruefe es intern.",
    ]

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))
    events = await collect(orch.run_turn(b"b", "turn.webm", "audio/webm"))

    assert completed(events).ends_call is False


@pytest.mark.parametrize(
    ("reply", "user_line", "expected"),
    [
        # The live case: the question read back, then the actual answer.
        (
            "Verzeihung, mit wem rede ich da? Ich bin Thomas Brandt.",
            "Verzeihung, mit wem rede ich da?",
            "Ich bin Thomas Brandt.",
        ),
        # Case and punctuation do not matter, only the words in order.
        ("ja sagen sie gerne mal was die frage ist -- also:", "Ja, sagen Sie gerne mal, was die Frage ist.", "also:"),
        # The whole chunk was the echo: nothing left to say from it.
        ("Verzeihung, mit wem rede ich da?", "Verzeihung, mit wem rede ich da?", ""),
        # A two-word pick-up is how people talk, not an echo.
        ("Ja gut, dann machen wir das so.", "Ja gut.", "Ja gut, dann machen wir das so."),
        # Sharing the first words is not reading the line back.
        ("Verzeihung, mit Ihrem Vertrag stimmt etwas nicht.", "Verzeihung, mit wem rede ich da?",
         "Verzeihung, mit Ihrem Vertrag stimmt etwas nicht."),
        # An echo further in is left alone -- only the opening is the tell.
        ("Also: mit wem rede ich da, fragen Sie?", "Mit wem rede ich da", "Also: mit wem rede ich da, fragen Sie?"),
    ],
)
def test_strip_echoed_prefix(reply, user_line, expected):
    assert strip_echoed_prefix(reply, user_line) == expected


@pytest.mark.parametrize(
    ("text", "said", "expected", "dropped"),
    [
        # A new opener, then a block already said, then something new.
        (
            "Nein, das passt nicht. Ich will eine konkrete Antwort, einen Namen oder ein Datum. "
            "Das Ticket ist offen.",
            {"ich will eine konkrete antwort, einen namen oder ein datum."},
            "Nein, das passt nicht. Das Ticket ist offen.",
            ["Ich will eine konkrete Antwort, einen Namen oder ein Datum."],
        ),
        # Short lines recur naturally and are never dropped.
        (
            "Ja, genau. Das sehe ich auch so.",
            {"ja, genau.", "das sehe ich auch so."},
            "Ja, genau. Das sehe ich auch so.",
            [],
        ),
        # Nothing said before: untouched.
        (
            "Alles neu hier, ganz ohne Wiederholung von irgendetwas.",
            set(),
            "Alles neu hier, ganz ohne Wiederholung von irgendetwas.",
            [],
        ),
    ],
)
def test_drop_said_sentences(text, said, expected, dropped):
    assert drop_said_sentences(text, said) == (expected, dropped)


async def test_a_block_carried_over_under_a_new_opener_is_dropped_before_it_is_spoken(
    persona, scenario, fake_pipeline
):
    block = "Das Ticket wurde vor elf Tagen geoeffnet, und ein Rueckruf war fest zugesagt."
    fake_pipeline.stt.transcripts = ["Ich schaue nach.", "Es tut mir leid, das dauert noch."]
    fake_pipeline.llm.replies = [
        f"{block} Ich brauche dazu bitte eine konkrete Zahl von Ihnen.",
        f"Das ist mir zu wenig. {block} Wann kann ich mit einer Antwort rechnen?",
    ]

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))
    events = await collect(orch.run_turn(b"b", "turn.webm", "audio/webm"))

    assert completed(events).ends_call is False
    assert orch.turns[1].persona_text == "Das ist mir zu wenig. Wann kann ich mit einer Antwort rechnen?"
    assert orch.history.messages[-1]["content"] == orch.turns[1].persona_text


async def test_a_reply_that_is_nothing_but_the_users_line_is_re_asked_once(persona, scenario, fake_pipeline):
    line = "36 Stunden, das geht nicht frueher."
    fake_pipeline.stt.transcripts = [line]
    fake_pipeline.llm.replies = [line, "Gut, dann nehme ich die 36 Stunden. Melden Sie sich bitte, sobald es laeuft."]

    orch = SessionOrchestrator(persona, scenario)
    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    assert completed(events).ends_call is False
    assert len(fake_pipeline.llm.calls) == 2
    retry = fake_pipeline.llm.calls[-1][-1]
    assert retry["role"] == "system"
    assert "repeated the user's own words" in retry["content"] and line in retry["content"]
    assert orch.turns[-1].persona_text.startswith("Gut, dann nehme ich die 36 Stunden")


async def test_an_echo_that_survives_the_re_ask_ends_the_call_with_the_sign_off_not_an_error(
    persona, scenario, fake_pipeline
):
    line = "36 Stunden, das geht nicht frueher."
    fake_pipeline.stt.transcripts = [line]
    fake_pipeline.llm.replies = [line, line]

    orch = SessionOrchestrator(persona, scenario)
    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    assert not any(isinstance(e, Failed) for e in events), "not an error"
    assert completed(events).ends_call is True
    assert FALLBACK_LINE in orch.turns[-1].persona_text
    assert line not in orch.turns[-1].persona_text


# Seen live: after two barge-ins the model reproduced a cut-off line verbatim.
_LINE_A = "Das ist ein Problem, das wir seit einem Monat haben, und es hat einen Supportversprechen gegeben."
_LINE_B = "Das Problem ist, dass die Ausfuhren fuer eines der zwei Konten nicht funktionieren, seit elf Tagen."


async def test_a_reply_opening_with_a_sentence_already_said_is_regenerated_not_spoken(
    persona, scenario, fake_pipeline, monkeypatch
):
    monkeypatch.setattr("backend.session.orchestrator.tts.duration_ms", lambda _wav: 10000)
    fake_pipeline.stt.transcripts = [
        "Was ist denn genau das Problem?",
        "Ich schaue mir das Ticket gerade an.",
        "Kann ich Ihnen eine Erstattung anbieten?",
    ]
    fake_pipeline.llm.replies = [
        f"{_LINE_A} Ich will wissen, wann es wieder funktioniert.",
        _LINE_B,
        f"{_LINE_A} Ich will—",            # the loop: line A again, dash and all
        "Eine Erstattung— ja, das waere ein Anfang, aber ich brauche auch einen Termin.",
    ]

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))
    # Line A played in full, "Ich will" of the second chunk, then the barge-in:
    # the history now holds "<line A> Ich will—", as in the live call.
    orch.note_late_barge_in(12000)
    assert orch.history.messages[-1]["content"] == f"{_LINE_A} Ich will—"
    await collect(orch.run_turn(b"b", "turn.webm", "audio/webm"))

    events = await collect(orch.run_turn(b"c", "turn.webm", "audio/webm"))

    assert completed(events).ends_call is False
    retry = fake_pipeline.llm.calls[-1]
    assert retry[-1]["role"] == "system" and "already said exactly that" in retry[-1]["content"]
    assert _LINE_A in retry[-1]["content"], "the repeated opening is quoted"
    spoken = orch.turns[-1].persona_text
    assert spoken.startswith("Eine Erstattung ja, das waere ein Anfang"), spoken
    assert "—" not in spoken and _LINE_A not in spoken


async def test_a_regeneration_that_loops_again_still_ends_the_call(
    persona, scenario, fake_pipeline
):
    fake_pipeline.stt.transcripts = ["Was ist denn genau das Problem?", "Ich schaue nach.", "Und jetzt?"]
    fake_pipeline.llm.replies = [_LINE_A, _LINE_B, _LINE_A, _LINE_A]

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))
    await collect(orch.run_turn(b"b", "turn.webm", "audio/webm"))
    events = await collect(orch.run_turn(b"c", "turn.webm", "audio/webm"))

    assert len(fake_pipeline.llm.calls) == 4, "exactly one regeneration"
    assert completed(events).ends_call is True


async def test_the_opening_checks_survive_a_first_chunk_the_filters_emptied(
    persona, scenario, fake_pipeline
):
    # Not the opening's first sentence, which the guard itself would catch.
    said = "Die Preisanpassung war um zwoelf Prozent, ohne jede Aenderung am Leistungsumfang."
    regreet = "Guten Tag, hier ist Thomas Brandt von der Firma Beispiel, es geht um die Kosten."
    clean = "Ich brauche dafuer eine belastbare Begruendung, sonst kommen wir hier nicht weiter."
    fake_pipeline.stt.transcripts = ["Was genau meinen Sie damit?"]
    fake_pipeline.llm.replies = [
        f"Guten Tag, hier ist Thomas Brandt. {said}",  # the opening turn
        f"{said} {regreet}",                           # chunk 1 emptied, chunk 2 re-greets
        clean,                                         # the regeneration
    ]

    orch = SessionOrchestrator(persona, scenario)
    await collect(orch.run_opening_turn())
    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    spoken = b"".join(c.audio for c in audio_chunks(events))
    assert b"hier ist Thomas Brandt" not in spoken, "the re-greeting never went out"
    assert orch.turns[-1].persona_text == clean
    assert len(fake_pipeline.llm.calls) == 3, "the second chunk was guarded, so one regeneration"
    assert completed(events).ends_call is False
