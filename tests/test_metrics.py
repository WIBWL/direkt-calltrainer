"""The Session's statistics, derived from a finished call.

Covers:
  F-24  talk share, and the unit it is a share *of*
  F-36  speaking pace, and the unit it is a rate *over*
  F-53  reaction time: only from Turns whose start was actually measured
  F-37  the loudness curve, and the words the wrap-up gets instead of its
        dB span
  ADR 0047/0048  a Turn's acoustics are measured inline and never load-bearing,
                 so a failed measurement stays visible downstream
  ADR 0051  no figure the user could take for measured when it was not
  F-53      every metric belongs to one half of the metrics slider (ADR 0082)
  F-51      phonation share: how much of the recording was speech
  F-41      open and closed questions, split off the same question marks
  F-51      lexical fillers, counted from the transcript per language (ADR 0083)
  F-08      passages said again word for word, one repeated sentence counting once
  ADR 0085  a recording with no detectable silence drops what rests on silence
  F-63      the opening (ADR 0086): greeting, own name and an offer of help (the concern,
            when the user rang), and its tempo
  F-65      the closing (ADR 0089): a recap, a concrete next step and a goodbye in the
            user's last two turns, the same whoever rang

`conversation()` and `measure()` are pure functions over in-memory Turns: no
database, no audio and no Praat -- the acoustic facts are handed in as the
numbers `analyze()` would have produced.
"""

import pytest

from backend.db.models import METRIC_ASPECTS
from backend.feedback.acoustics import Pause
from backend.feedback.metrics import METRICS, describe_loudness_course, measure
from backend.session.models import Turn, conversation

# A recording that ran 4 s and held 2 s of speech: the two figures these tests
# keep apart.
_AUDIO_MS = 4_000
_PHONATION_MS = 2_000


def _measured_call() -> list[Turn]:
    """A two-Turn call, fully measured: the Persona opens, then one exchange."""
    return [
        Turn(seq=1, persona_text="Guten Tag.", persona_offset_ms=0, persona_end_ms=1_000),
        Turn(
            seq=2,
            user_text="Zwei Woerter",
            user_offset_ms=1_500,
            user_end_ms=1_500 + _AUDIO_MS,
            user_speech_ms=_AUDIO_MS,
            user_phonation_ms=_PHONATION_MS,
            persona_text="Verstanden.",
            persona_offset_ms=6_000,
            persona_end_ms=7_000,
        ),
    ]


def _by_key(turns: list[Turn]) -> dict[str, float]:
    return {m.key: m.value for m in measure(conversation(turns))}


def test_every_metric_belongs_to_one_half_of_the_grid() -> None:
    """provision.py seeds `metric_type.aspect` from this inventory: a value
    outside the vocabulary fails to seed, a missing one is filed under "what"
    by the screen's fallback rather than showing up as a fault."""
    assert all(metric.aspect in METRIC_ASPECTS for metric in METRICS)


def test_both_halves_of_the_grid_are_measured() -> None:
    """The slider hides itself when one half is empty (FeedbackView.tsx)."""
    assert {metric.aspect for metric in METRICS if metric.active} == set(METRIC_ASPECTS)


def test_talk_share_compares_audio_duration_on_both_sides() -> None:
    """F-24. Audio duration on both sides -- 4 s of user against 2 s of Persona
    is two thirds. A silence-stripped numerator over an un-stripped denominator
    would report Praat's segmentation as a smaller share (here, half)."""
    values = _by_key(_measured_call())

    assert values["talk_share"] == 4_000 * 100 / (4_000 + 2_000)


def test_talk_share_detail_reports_the_same_unit_it_divided() -> None:
    """ADR 0029's detail carries the milliseconds the share was computed from,
    so a reader can check the percentage against them."""
    call = conversation(_measured_call())
    detail = next(m for m in measure(call) if m.key == "talk_share").detail

    assert detail == {"user_ms": _AUDIO_MS, "persona_ms": 2_000}


def test_pace_divides_by_phonation_not_by_the_recording() -> None:
    """F-36. Words per minute of talking: the silences inside the utterance and
    the VAD's padding are not time the user spoke in. Two words in 2 s of
    phonation is 60 wpm; over the 4 s recording it would read as 30."""
    values = _by_key(_measured_call())

    assert values["pace"] == 60.0


def test_reaction_time_is_measured_from_when_the_persona_stopped() -> None:
    """F-53. Reply at 1500 ms, Persona stopped at 1000 ms: half a second, with
    the gateway's latency outside the window by construction (ADR 0051)."""
    assert conversation(_measured_call()).reactions_ms == (500,)


# --- A Turn that could not be measured (ADR 0048) --------------------------


def _call_with_one_unmeasured_turn() -> list[Turn]:
    """The same call plus a Turn whose acoustics failed: words (STT succeeded),
    no milliseconds, and `user_offset_ms` on its fallback -- the *end* of the
    user's speech, the only point the server knows without a duration."""
    return _measured_call() + [
        Turn(
            seq=3,
            user_text="Diese Antwort wurde nicht gemessen",
            user_offset_ms=12_000,
            user_end_ms=12_000,
            user_acoustics_complete=False,
        ),
    ]


def test_redefluss_is_the_share_of_the_recording_that_was_speech() -> None:
    """F-51. 2 s of speech in a 4 s recording is 50%."""
    assert _by_key(_measured_call())["phonation_share"] == 50.0


def test_redefluss_is_absent_where_the_acoustics_failed() -> None:
    """ADR 0048: both figures are short by an unknown amount."""
    assert "phonation_share" not in _by_key(_call_with_one_unmeasured_turn())


def _questions_asked(text: str, language_id: str | None = "de"):
    """The questions Measurement for a call in which the user said `text`."""
    found = [m for m in measure(conversation([Turn(seq=1, user_text=text)], language_id))
             if m.key == "questions"]
    assert found, "no questions measurement"
    return found[0]


def test_open_and_closed_questions_add_up_to_the_count() -> None:
    """F-41. Both halves come off the same question marks, so the tile showing
    the count and the split cannot contradict itself."""
    asked = _questions_asked("Was brauchen Sie? Passt Ihnen Dienstag? Wirklich?")

    assert asked.value == 3
    assert (asked.detail["open"], asked.detail["closed"]) == (1, 2)


def test_a_question_is_read_from_where_it_begins_not_from_the_sentence_before() -> None:
    """The transcript runs sentences together; the question is the last clause
    before the mark."""
    assert _questions_asked("Das ist klar. Wann passt es Ihnen?").detail["open"] == 1


def test_the_split_follows_the_language_the_call_ran_in() -> None:
    """The question words come from the Persona's language pack."""
    asked = _questions_asked("What do you need? Does Tuesday work?", language_id="en")

    assert (asked.detail["open"], asked.detail["closed"]) == (1, 1)


def test_questions_are_still_counted_without_a_language() -> None:
    """The count is punctuation and needs no vocabulary."""
    asked = _questions_asked("Was brauchen Sie?", language_id=None)

    assert asked.value == 1
    assert "open" not in asked.detail


def _fillers_in(text: str, language_id: str | None = "de"):
    """The fillers Measurement for a call in which the user said `text`, or None."""
    found = [m for m in measure(conversation([Turn(seq=1, user_text=text)], language_id))
             if m.key == "fillers"]
    return found[0] if found else None


def test_fillers_are_counted_per_word_from_the_transcript() -> None:
    """F-51. Case-insensitive, and a phrase counts once, as itself."""
    counted = _fillers_in("Eigentlich passt das. Das ist halt so, sag ich mal, eigentlich.")

    assert counted.value == 4
    assert counted.detail["words"] == {"eigentlich": 2, "halt": 1, "sag ich mal": 1}


def test_a_filler_inside_another_word_is_not_one() -> None:
    """"Haltung" and "enthalten" both contain "halt"."""
    assert _fillers_in("Die Haltung ist enthalten.").value == 0


def test_fillers_follow_the_language_of_the_call() -> None:
    """The list comes from the Persona's language pack."""
    assert _fillers_in("Basically, you know, it works.", language_id="en").value == 2


def test_fillers_need_a_vocabulary() -> None:
    """No pack means no list: absent, rather than a zero that looks measured."""
    assert _fillers_in("Eigentlich schon.", language_id=None) is None


def _repetitions_in(text: str):
    """The repetitions Measurement for a call in which the user said `text`."""
    return next(m for m in measure(conversation([Turn(seq=1, user_text=text)], "de"))
                if m.key == "repetitions")


def test_a_repeated_sentence_counts_once_and_is_quoted() -> None:
    """F-08. Its overlapping four-word matches merge into one passage."""
    said = _repetitions_in(
        "Die Lieferung ist leider unvollständig. Also die Lieferung ist leider unvollständig."
    )

    assert said.value == 1
    assert said.detail["passages"] == ["die Lieferung ist leider unvollständig"]


def test_three_repeated_words_are_no_repetition() -> None:
    """"Ich habe das" twice is how people talk, not saying something twice."""
    assert _repetitions_in("Ich habe das gesehen. Ich habe das gelesen.").value == 0


def test_stammering_does_not_repeat_itself() -> None:
    """A run of one word would otherwise match its own overlapping copies."""
    assert _repetitions_in("ja ja ja ja ja ja").value == 0


def test_a_recording_without_silence_drops_what_rests_on_silence() -> None:
    """A noise floor above the threshold leaves nothing silent: pauses, phonation share,
    pace and the loudness span would report the noise as speech. Talk share
    rests on the recording's length and stays."""
    turns = _measured_call()
    turns[1].loudness_db = [60.0] * 100

    keys = set(_by_key(turns))

    assert not {"pauses", "phonation_share", "pace", "loudness"} & keys
    assert "talk_share" in keys


def test_ordinary_silence_keeps_them() -> None:
    """Stored calls are 37 to 67 % silent; half is well clear of the cut-off."""
    turns = _measured_call()
    turns[1].loudness_db = [60.0, None] * 50

    assert {"phonation_share", "pace", "loudness"} <= set(_by_key(turns))


def _opening_of(*said: tuple[str, int], language_id: str | None = "de", reverse=False):
    """The opening Measurement for a call whose user turns were `said`, as
    (text, phonation ms), after the Persona's own opening line."""
    turns = [Turn(seq=1, persona_text="Brandt hier, ich rufe wegen der Lieferung an.")]
    turns += [Turn(seq=i + 2, user_text=text, user_speech_ms=ms, user_phonation_ms=ms)
              for i, (text, ms) in enumerate(said)]
    found = [m for m in measure(conversation(turns, language_id, reverse))
             if m.key == "opening"]
    return found[0] if found else None


def test_an_opening_with_all_three_parts() -> None:
    """F-63. The called side: greeting, name, and an offer of help."""
    opening = _opening_of(("Guten Tag, hier ist Schmidt. Was kann ich für Sie tun?", 3000))

    assert opening.value == 3
    assert (opening.detail["greeting"], opening.detail["name"], opening.detail["offer"]) == (
        True, True, True)


def test_the_caller_states_the_concern_instead() -> None:
    """In a reverse the user rang, so the concern is named, not asked for."""
    opening = _opening_of(("Hallo, mein Name ist Beck, ich rufe an wegen der Rechnung.", 3000),
                          reverse=True)

    assert opening.value == 3
    assert "offer" not in opening.detail


def test_each_side_is_checked_for_its_own_part() -> None:
    """Stating a concern is no offer of help, and an offer is no concern."""
    called = _opening_of(("Guten Tag, ich rufe an wegen der Rechnung.", 2000))
    calling = _opening_of(("Guten Tag, was kann ich für Sie tun?", 2000), reverse=True)

    assert called.detail["offer"] is False
    assert calling.detail["concern"] is False


def test_a_frame_without_a_name_is_no_introduction() -> None:
    """"hier ist alles" and "hier ist Ihr Ansprechpartner" name nobody."""
    for said in ("Hier ist alles in Ordnung.", "Hier ist Ihr Ansprechpartner."):
        assert _opening_of((said, 2000)).detail["name"] is False


def test_the_opening_follows_the_language_of_the_call() -> None:
    """The patterns come from the Persona's language pack."""
    opening = _opening_of(("Hello, this is Sarah. How can I help?", 2000), language_id="en")

    assert opening.value == 3


def test_i_am_introduces_a_name_in_english() -> None:
    """"I'm Alice" is how most English speakers say it; "I'm fine" names nobody."""
    assert _opening_of(("Hi Samantha, I'm Alice.", 2000), language_id="en").detail["name"]
    assert not _opening_of(("I'm fine, thanks.", 2000), language_id="en").detail["name"]


def test_the_opening_needs_a_vocabulary() -> None:
    """No pack means no patterns: absent, not a zero that looks measured."""
    assert _opening_of(("Guten Tag.", 1000), language_id=None) is None


def test_the_opening_tempo_is_read_against_the_rest_of_the_call() -> None:
    """Ten words in 2 s against twenty in 8 s: twice the user's own rate."""
    opening = _opening_of(
        ("Guten Tag hier ist Schmidt womit kann ich Ihnen helfen", 2000),
        ("eins zwei drei vier fünf sechs sieben acht neun zehn "
         "elf zwölf dreizehn vierzehn fünfzehn sechzehn siebzehn achtzehn neunzehn zwanzig", 8000),
    )

    assert opening.detail["pace_ratio"] == pytest.approx(2.0)


def test_a_call_with_one_turn_has_no_tempo_to_compare() -> None:
    """Without a rest of the call there is nothing to be faster or slower than."""
    assert _opening_of(("Guten Tag, hier ist Schmidt.", 2000)).detail["pace_ratio"] is None


# The first two user turns of every closing test below: an opening and one
# answer, so the closing's window of two never reaches back into the greeting.
_BEFORE_THE_CLOSE = ("Guten Tag, hier ist Schmidt.", "Ja, das Gerät startet nicht mehr.")


def _closing_of(*last: str, language_id: str | None = "de", reverse=False):
    """The closing Measurement for a call whose user turns end in `last`."""
    turns = [Turn(seq=1, persona_text="Brandt hier, ich rufe wegen der Lieferung an.")]
    turns += [Turn(seq=i + 2, user_text=text, user_speech_ms=1000, user_phonation_ms=1000)
              for i, text in enumerate((*_BEFORE_THE_CLOSE, *last))]
    found = [m for m in measure(conversation(turns, language_id, reverse))
             if m.key == "closing"]
    return found[0] if found else None


def _parts(measurement) -> tuple[bool, bool, bool]:
    return (measurement.detail["recap"], measurement.detail["agreement"],
            measurement.detail["farewell"])


def test_a_closing_with_all_three_parts() -> None:
    """ADR 0089. A recap, a concrete next step and a goodbye, spread over the
    last two turns the way they usually are: the recap and the step, the
    Persona's answer, then the goodbye."""
    closing = _closing_of(
        "Ich fasse kurz zusammen: Wir tauschen das Gerät. Ich schicke Ihnen bis Freitag "
        "die Bestätigung.",
        "Danke für Ihren Anruf, auf Wiederhören.",
    )

    assert closing.value == 3
    assert _parts(closing) == (True, True, True)
    assert closing.detail["turns_read"] == 2


def test_the_closing_reads_only_the_last_two_turns() -> None:
    """A recap three turns before the end is not the closing -- at six to nine
    turns a call, three would be a third of it."""
    closing = _closing_of(
        "Wir haben also vereinbart, dass Sie das Gerät einschicken.",
        "Ja, genau so.",
        "Tschüss.",
    )

    assert _parts(closing) == (False, False, True)


def test_a_call_too_short_to_have_a_closing_has_none() -> None:
    """Under three user turns the window would reach back into the opening:
    absent, not a zero that looks measured."""
    turns = [Turn(seq=1, persona_text="Guten Tag."),
             Turn(seq=2, user_text="Hallo, auf Wiederhören.", user_speech_ms=1000,
                  user_phonation_ms=1000)]
    assert not [m for m in measure(conversation(turns, "de")) if m.key == "closing"]


def test_a_vague_promise_is_no_agreement() -> None:
    """"Ich kümmere mich darum" commits to nothing a caller could hold anyone to
    -- the phrase the Persona's own prompt calls a vague reassurance."""
    closing = _closing_of("Ich kümmere mich darum.", "Tschüss.")

    assert closing.detail["agreement"] is False


def test_a_question_about_how_is_no_agreement() -> None:
    """"Wie machen wir das?" asks for the next step; it does not settle one."""
    closing = _closing_of("Und wie machen wir das jetzt?", "Gut.")

    assert closing.detail["agreement"] is False


def test_a_greeting_is_no_farewell() -> None:
    """"Schönen guten Tag" is how a call starts, not how it ends."""
    closing = _closing_of("Schönen guten Tag nochmal.", "Ja.")

    assert closing.detail["farewell"] is False


def test_the_closing_is_the_same_whoever_rang() -> None:
    """Unlike the opening, whose third part depends on who rang, a good close
    asks the same of both sides."""
    said = ("Ich melde mich bis Montag bei Ihnen.", "Einen schönen Tag noch.")

    assert _parts(_closing_of(*said)) == _parts(_closing_of(*said, reverse=True))


def test_the_closing_follows_the_language_of_the_call() -> None:
    """The patterns come from the Persona's language pack."""
    closing = _closing_of(
        "Just to recap, I'll send you the new contract by Friday.",
        "Thanks for your time, goodbye.",
        language_id="en",
    )

    assert closing.value == 3


def test_the_closing_needs_a_vocabulary() -> None:
    """No pack means no patterns: absent rather than three misses."""
    assert _closing_of("Auf Wiederhören.", "Tschüss.", language_id=None) is None


def test_an_unmeasured_turn_contributes_no_reaction_time() -> None:
    """F-53/ADR 0048. Its offset is the end of the utterance, not the start, so
    reading it as a reaction time would report the utterance as hesitation. The
    measured Turn's 500 ms survives; nothing is invented for the other."""
    assert conversation(_call_with_one_unmeasured_turn()).reactions_ms == (500,)


def test_incomplete_acoustics_suppress_the_metrics_that_depend_on_them() -> None:
    """ADR 0048/0051. The failed Turn's words count while its milliseconds do
    not, so a share and a rate across the call would both come out low -- and a
    figure indistinguishable from a measured one is what ADR 0051 refuses to
    print. Transcript-only metrics never needed the audio."""
    keys = set(_by_key(_call_with_one_unmeasured_turn()))

    assert "talk_share" not in keys
    assert "pace" not in keys
    assert {"word_count", "questions"} <= keys


def test_the_opening_turn_does_not_count_as_a_failed_measurement() -> None:
    """The Persona speaks first, so the opening Turn has no user audio. Counting
    it as unmeasured would suppress the acoustic metrics of every call."""
    assert conversation(_measured_call()).user_acoustics_complete is True


def test_words_without_measured_speech_still_suppress_the_share() -> None:
    """A call whose Turns claim to be measured but carry no milliseconds is a
    measurement that failed without saying so, not a user who never spoke."""
    turns = [
        Turn(seq=1, persona_text="Guten Tag.", persona_offset_ms=0, persona_end_ms=1_000),
        Turn(seq=2, user_text="Ich habe gesprochen", user_offset_ms=1_500, user_end_ms=3_000),
    ]

    assert "talk_share" not in set(_by_key(turns))


def test_pauses_come_from_the_same_segmentation_as_phonation() -> None:
    """F-51. One Praat pass yields both, so the time by which phonation falls
    short of the recording is accounted for as pauses."""
    turns = _measured_call()
    turns[1].pauses = [Pause(offset_ms=2_000, duration_ms=1_000)]

    values = _by_key(turns)

    assert values["pauses"] == 1.0


# --- F-53: how long the user speaks before breaking off ---------------------
# Mean length of runs. A run is bounded by a pause inside an utterance or by
# the utterance itself, so the runs of a call are its pauses plus its
# utterances. The tests below pin that arithmetic, because it is the whole
# metric and it is off by one in either direction if the boundaries are counted
# wrong.


def test_an_uninterrupted_utterance_is_one_run() -> None:
    """No pause inside it, so the whole speaking time is a single stretch and
    the figure is that stretch."""
    values = _by_key(_measured_call())

    assert values["run_length"] == _PHONATION_MS / 1_000


def test_a_pause_inside_an_utterance_splits_it_into_two_runs() -> None:
    """The point of the metric. The speaking time has not changed and the
    phonation share has not changed; what changed is that it came out in two
    pieces instead of one, and this is the only figure that says so."""
    turns = _measured_call()
    turns[1].pauses = [Pause(offset_ms=2_000, duration_ms=500)]

    values = _by_key(turns)

    assert values["run_length"] == _PHONATION_MS / 2 / 1_000
    # ... while the two figures about the silence are unmoved by the split.
    assert values["phonation_share"] == _by_key(_measured_call())["phonation_share"]


def test_the_detail_carries_both_terms_of_the_denominator() -> None:
    """A call of many short utterances and one of few interrupted ones reach
    the same run count by different routes, and the figure alone cannot be read
    back into either."""
    turns = _measured_call()
    turns[1].pauses = [Pause(offset_ms=2_000, duration_ms=500)]

    detail = {m.key: m.detail for m in measure(conversation(turns))}["run_length"]

    assert detail["utterances"] == 1
    assert detail["pause_count"] == 1
    assert detail["runs"] == 2
    assert detail["phonation_ms"] == _PHONATION_MS


def test_an_unmeasured_turn_suppresses_the_run_length() -> None:
    """Phonation short by an unknown amount over a run count that is not,
    which is a figure nobody can interpret. Withheld for the whole call, the
    same trade ADR 0051 makes for the other acoustic statistics."""
    assert "run_length" not in set(_by_key(_call_with_one_unmeasured_turn()))


def test_a_call_the_user_never_spoke_in_has_no_run_length() -> None:
    """The opening Turn carries no user audio. Dividing by zero utterances
    would be an exception; reporting nothing is the answer."""
    turns = [Turn(seq=1, persona_text="Guten Tag.", persona_offset_ms=0, persona_end_ms=1_000)]

    assert "run_length" not in set(_by_key(turns))


def test_the_run_length_carries_no_step_and_no_colour() -> None:
    """It correlates with what listeners hear (Hincks 2005, r = 0.72, ahead of
    the pitch variation quotient F-35's reading rests on) and that is still not
    a boundary. Nothing published says where a short run stops being
    conversational, so ADR 0078's first condition is unmet and this stays a
    bare figure."""
    detail = {m.key: m.detail for m in measure(conversation(_measured_call()))}["run_length"]

    assert "light" not in detail
    assert "step" not in detail


# --- F-51: cutting in on the Persona (ADR 0035) ----------------------------


def _call_with_a_barge_in() -> list[Turn]:
    """A call where the user genuinely cut in: their utterance starts while the
    Persona's line still had seconds of audio outstanding, and that line was
    trimmed back to the heard part.

    Both halves are needed. A trimmed reply on its own says nothing about
    timing, and an overlap on its own may have cost the Persona nothing.
    """
    return [
        Turn(seq=1, persona_text="Guten Tag, ich rufe an wegen der offenen Rechnung ...",
             persona_offset_ms=0, persona_end_ms=10_000, persona_interrupted=True),
        Turn(
            seq=2,
            user_text="Moment bitte",
            user_offset_ms=3_000,
            user_end_ms=3_000 + _AUDIO_MS,
            user_speech_ms=_AUDIO_MS,
            user_phonation_ms=_PHONATION_MS,
            persona_text="Gut.",
            persona_offset_ms=12_000,
            persona_end_ms=13_000,
        ),
    ]


def test_an_interruption_needs_both_the_overlap_and_the_lost_words() -> None:
    """The event is "the Persona had more to say and did not get to say it".
    Read off the timeline plus the trim flag, never off the transcript's
    "[unterbrochen]" marker, which is a rendering decision."""
    values = _by_key(_call_with_a_barge_in())

    assert values["interruptions"] == 1.0


def test_a_trimmed_reply_the_user_did_not_overlap_is_not_an_interruption() -> None:
    """Same flag, no overlapping start: whatever cut that reply short, it was
    not somebody talking over it."""
    turns = _measured_call()
    turns[1].persona_interrupted = True

    assert _by_key(turns)["interruptions"] == 0.0


def test_a_call_nobody_interrupted_reports_zero_rather_than_nothing() -> None:
    """Zero is a measurement here, unlike elsewhere in this module. The user
    let every reply finish, which is a fact about the call; a missing row would
    read as "not measured" and hide it."""
    values = _by_key(_measured_call())

    assert values["interruptions"] == 0.0


def test_the_count_carries_its_context_without_dividing_by_it() -> None:
    """A count, with the number of Persona replies beside it rather than under
    it. A rate was built and dropped: at the length these calls run, dividing
    turned a single interruption into the top step of the scale, which said
    more about the denominator than about the call.

    The offsets travel too, so the interface can point at them in the
    transcript without recomputing anything.
    """
    detail = next(
        m.detail for m in measure(conversation(_call_with_a_barge_in()))
        if m.key == "interruptions"
    )

    assert detail["persona_turns"] == 2
    assert detail["soft_count"] == 0
    assert detail["hard_offsets_ms"] == [3_000]
    assert "interruption_rate" not in {m.key for m in measure(conversation(_measured_call()))}


def test_a_call_with_no_persona_reply_yields_no_interruption_figure() -> None:
    """Nothing was there to cut into, so there is nothing to report. Zero would
    claim the user restrained themselves."""
    turns = [Turn(seq=1, user_text="Hallo?", user_speech_ms=500, user_phonation_ms=400)]

    assert "interruptions" not in _by_key(turns)


# --- F-35: the pitch range, in an interval rather than in Hertz ------------


def test_intonation_is_reported_in_semitones() -> None:
    """A fifth is seven semitones. In Hertz the same figure would describe the
    voice rather than what was done with it."""
    turns = _measured_call()
    turns[1].pitch_hz = [120.0] * 30 + [180.0] * 30

    values = _by_key(turns)

    assert values["intonation"] == pytest.approx(7.02, abs=0.6)


def test_an_unvoiced_call_has_no_pitch_figure() -> None:
    """Whispering, or a Turn Praat found no voicing in. A span over nothing
    would be a number with no measurement behind it."""
    turns = _measured_call()
    turns[1].pitch_hz = [None] * 60

    assert "intonation" not in _by_key(turns)


def test_a_handful_of_voiced_frames_is_not_a_range() -> None:
    """Below the floor the percentiles are picking single frames, and one
    octave error would then decide the value for the whole call."""
    turns = _measured_call()
    turns[1].pitch_hz = [120.0, 240.0, 130.0]

    assert "intonation" not in _by_key(turns)


def test_the_curve_carries_the_seams_between_the_users_turns() -> None:
    """The drawn curve is the user's speaking time with the Persona's turns
    taken out, so the point where one of their utterances ends and the next
    begins is not recoverable from the curve itself. Without it a seam would be
    read as a movement of the voice.

    No step is stored beside it: which step of the scale the figure lands on is
    derived when the Session is read (`api/sessions.py::_served_detail`), so a
    recalibration reaches trainings whose audio is long gone.
    """
    turns = _measured_call()
    turns[1].pitch_hz = [120.0] * 60
    turns.append(
        Turn(
            seq=3,
            user_text="Und noch etwas",
            user_offset_ms=8_000,
            user_end_ms=8_000 + _AUDIO_MS,
            user_speech_ms=_AUDIO_MS,
            user_phonation_ms=_PHONATION_MS,
            pitch_hz=[150.0] * 60,
        )
    )

    detail = next(m.detail for m in measure(conversation(turns)) if m.key == "intonation")

    # 60 frames at 10 ms thinned to the 50 ms display grid is 12 points each.
    assert detail["curve_step_ms"] == 50
    assert detail["turn_breaks"] == [12]
    assert len(detail["curve_hz"]) == 24
    assert "liveliness" not in detail


# --- F-37: the loudness course, described rather than scored ---------------

# Steady without being constant: real Praat output jitters a few dB per frame,
# and a spread of exactly zero is what would make the band degenerate.
def _steady(points: int, level: float = 65.0) -> list[float | None]:
    return [level + (index % 5) - 2 for index in range(points)]


def _with_stretch(shift: float, length: int, at: int) -> list[float | None]:
    """A steady 60 s call with one shifted stretch spliced into it."""
    curve = _steady(600)
    for index in range(at, at + length):
        value = curve[index]
        assert value is not None
        curve[index] = value + shift
    return curve


def test_an_even_call_is_described_as_even() -> None:
    """The band comes from the call's own samples, so a speaker who held one
    level never leaves it. A flat call must not be given a variation."""
    assert "even" in describe_loudness_course(_steady(600))


def test_a_sustained_shift_is_named_with_where_it_happened() -> None:
    """What F-37 is for -- and the most that can be said without the norms
    ADR 0051 declined to invent."""
    described = describe_loudness_course(_with_stretch(shift=10.0, length=60, at=450))

    assert "louder stretch" in described
    assert "in the final third" in described


def test_a_brief_change_is_not_a_stretch() -> None:
    """One second outside the band is a stressed word. Marking it would bury
    the sustained shifts."""
    assert "even" in describe_loudness_course(_with_stretch(shift=10.0, length=10, at=450))


def test_a_shift_covering_a_third_of_the_call_is_still_found() -> None:
    """The regression the band exists to avoid: a stretch that long *is* the
    tenth percentile. The median absolute deviation survives it."""
    described = describe_loudness_course(_with_stretch(shift=-9.0, length=200, at=380))

    assert "quieter stretch" in described


def test_both_directions_are_reported_when_both_happened() -> None:
    """A call that rose and later fell is two observations, which is why the
    stretches are kept per direction."""
    curve = _with_stretch(shift=10.0, length=60, at=60)
    for index in range(430, 490):
        value = curve[index]
        assert value is not None
        curve[index] = value - 9.0

    described = describe_loudness_course(curve)

    assert "louder stretch" in described
    assert "quieter stretch" in described


def test_the_description_carries_no_figure_and_no_timestamp() -> None:
    """ADR 0051: a dB reading in the prompt comes back out as one in the
    wrap-up, over a chart that shows none. A timestamp would be read against the
    transcript's clock, which this curve is not on."""
    described = describe_loudness_course(_with_stretch(shift=10.0, length=60, at=450))

    assert not any(character.isdigit() for character in described)
    assert "dB" not in described


def test_a_call_with_almost_no_audible_speech_says_so() -> None:
    """Saying "even" about two samples reports a steadiness never measured."""
    assert "too little" in describe_loudness_course([None] * 40 + [65.0, 66.0])
