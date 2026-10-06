"""The metrics derived from a finished call (F-08, F-24, F-36, F-37, F-41, F-51, F-53, F-63, F-65, ADR 0051, 0085)."""

import re
from pathlib import Path

import pytest

from shared.db.models import METRIC_ASPECTS
from shared.feedback.acoustics import Pause
from shared.feedback.metrics import METRICS, describe_loudness_course, measure
from shared.feedback.calls import conversation
from shared.turn import Turn

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
    assert all(metric.aspect in METRIC_ASPECTS for metric in METRICS)


def test_both_halves_of_the_grid_are_measured() -> None:
    assert {metric.aspect for metric in METRICS if metric.active} == set(METRIC_ASPECTS)


_PAUSE_MS = 500


def _call_with_a_pause() -> list[Turn]:
    """2 s speech + 0.5 s pause = 2.5 s span inside a 4 s recording."""
    turns = _measured_call()
    turns[1].pauses = [Pause(offset_ms=2_000, duration_ms=_PAUSE_MS)]
    return turns


def test_talk_share_counts_the_user_from_first_sound_to_last() -> None:
    values = _by_key(_call_with_a_pause())

    assert values["talk_share"] == 2_500 * 100 / (2_500 + 2_000)


def test_talk_share_detail_reports_the_same_unit_it_divided() -> None:
    call = conversation(_call_with_a_pause())
    detail = next(m for m in measure(call) if m.key == "talk_share").detail

    assert detail == {"user_ms": _PHONATION_MS + _PAUSE_MS, "persona_ms": 2_000}


def test_pace_divides_by_phonation_not_by_the_recording() -> None:
    values = _by_key(_measured_call())

    assert values["pace"] == 60.0


def test_reaction_time_is_measured_from_when_the_persona_stopped() -> None:
    assert [r.gap_ms for r in conversation(_measured_call()).reactions] == [500]


def _call_with_one_unmeasured_turn() -> list[Turn]:
    """Plus a Turn whose acoustics failed: words, no milliseconds."""
    return _measured_call() + [
        Turn(
            seq=3,
            user_text="Diese Antwort wurde nicht gemessen",
            user_offset_ms=12_000,
            user_end_ms=12_000,
            user_acoustics_complete=False,
        ),
    ]


def test_redefluss_is_the_share_of_the_span_that_was_speech() -> None:
    assert _by_key(_call_with_a_pause())["phonation_share"] == 80.0


def test_redefluss_without_a_pause_is_complete() -> None:
    assert _by_key(_measured_call())["phonation_share"] == 100.0


def test_redefluss_detail_names_the_span_it_divided_by() -> None:
    detail = {m.key: m.detail for m in measure(conversation(_call_with_a_pause()))}

    assert detail["phonation_share"] == {"voiced_ms": 2_500, "phonation_ms": _PHONATION_MS}


def test_redefluss_is_absent_where_the_acoustics_failed() -> None:
    assert "phonation_share" not in _by_key(_call_with_one_unmeasured_turn())


def _questions_asked(text: str, language_id: str | None = "de"):
    """The questions Measurement for a call in which the user said `text`."""
    found = [m for m in measure(conversation([Turn(seq=1, user_text=text)], language_id))
             if m.key == "questions"]
    assert found, "no questions measurement"
    return found[0]


def test_open_and_closed_questions_add_up_to_the_count() -> None:
    asked = _questions_asked("Was brauchen Sie? Passt Ihnen Dienstag? Wirklich?")

    assert asked.value == 3
    assert (asked.detail["open"], asked.detail["closed"]) == (1, 2)


def test_a_question_is_read_from_where_it_begins_not_from_the_sentence_before() -> None:
    assert _questions_asked("Das ist klar. Wann passt es Ihnen?").detail["open"] == 1


def test_the_split_follows_the_language_the_call_ran_in() -> None:
    asked = _questions_asked("What do you need? Does Tuesday work?", language_id="en")

    assert (asked.detail["open"], asked.detail["closed"]) == (1, 1)


def test_questions_are_still_counted_without_a_language() -> None:
    asked = _questions_asked("Was brauchen Sie?", language_id=None)

    assert asked.value == 1
    assert "open" not in asked.detail


def _fillers_in(text: str, language_id: str | None = "de"):
    """The fillers Measurement for a call in which the user said `text`, or None."""
    found = [m for m in measure(conversation([Turn(seq=1, user_text=text)], language_id))
             if m.key == "fillers"]
    return found[0] if found else None


def test_fillers_are_counted_per_word_from_the_transcript() -> None:
    counted = _fillers_in("Eigentlich passt das. Das ist halt so, sag ich mal, eigentlich.")

    assert counted.value == 4
    assert counted.detail["words"] == {"eigentlich": 2, "halt": 1, "sag ich mal": 1}


def test_a_filler_inside_another_word_is_not_one() -> None:
    assert _fillers_in("Die Haltung ist enthalten.").value == 0


def test_fillers_follow_the_language_of_the_call() -> None:
    assert _fillers_in("Basically, you know, it works.", language_id="en").value == 2


def test_fillers_need_a_vocabulary() -> None:
    assert _fillers_in("Eigentlich schon.", language_id=None) is None


def _repetitions_in(text: str):
    """The repetitions Measurement for a call in which the user said `text`."""
    return next(m for m in measure(conversation([Turn(seq=1, user_text=text)], "de"))
                if m.key == "repetitions")


def test_a_repeated_sentence_counts_once_and_is_quoted() -> None:
    said = _repetitions_in(
        "Die Lieferung ist leider unvollständig. Also die Lieferung ist leider unvollständig."
    )

    assert said.value == 1
    assert said.detail["passages"] == ["die Lieferung ist leider unvollständig"]


def test_three_repeated_words_are_no_repetition() -> None:
    assert _repetitions_in("Ich habe das gesehen. Ich habe das gelesen.").value == 0


def test_stammering_does_not_repeat_itself() -> None:
    assert _repetitions_in("ja ja ja ja ja ja").value == 0


def test_a_recording_without_silence_drops_what_rests_on_silence() -> None:
    turns = _measured_call()
    turns[1].loudness_db = [60.0] * 100

    keys = set(_by_key(turns))

    assert not {"pauses", "phonation_share", "pace", "loudness",
                "run_length", "talk_share"} & keys


def test_ordinary_silence_keeps_them() -> None:
    turns = _measured_call()
    turns[1].loudness_db = [60.0, None] * 50

    assert {"phonation_share", "pace", "loudness", "run_length"} <= set(_by_key(turns))


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
    opening = _opening_of(("Guten Tag, hier ist Schmidt. Was kann ich für Sie tun?", 3000))

    assert opening.value == 3
    assert (opening.detail["greeting"], opening.detail["name"], opening.detail["offer"]) == (
        True, True, True)


def test_the_caller_states_the_concern_instead() -> None:
    opening = _opening_of(("Hallo, mein Name ist Beck, ich rufe an wegen der Rechnung.", 3000),
                          reverse=True)

    assert opening.value == 3
    assert "offer" not in opening.detail


def test_each_side_is_checked_for_its_own_part() -> None:
    called = _opening_of(("Guten Tag, ich rufe an wegen der Rechnung.", 2000))
    calling = _opening_of(("Guten Tag, was kann ich für Sie tun?", 2000), reverse=True)

    assert called.detail["offer"] is False
    assert calling.detail["concern"] is False


def test_a_frame_without_a_name_is_no_introduction() -> None:
    for said in ("Hier ist alles in Ordnung.", "Hier ist Ihr Ansprechpartner.",
                 "Hier sind Ihre Unterlagen."):
        assert _opening_of((said, 2000)).detail["name"] is False


@pytest.mark.parametrize("said", [
    # Found in testing, each one an opening the check did not see.
    "Guten Tag, hier ist die Anna.",       # an article before a first name
    "Guten Tag, hier spricht der Peter.",
    "Guten Tag, Sie sprechen mit Anna Beck.",  # the standard service phrasing
    "Guten Tag, hier Beck.",               # the frame without its verb
    "Mein Name: Beck.",
    "Hier ist Frau Beck.",
])
def test_the_frames_a_name_is_actually_said_in(said: str) -> None:
    assert _opening_of((said, 2000)).detail["name"] is True


def test_a_bare_surname_is_still_not_recognised() -> None:
    assert _opening_of(("Beck, guten Tag.", 2000)).detail["name"] is False


def test_you_are_speaking_with_introduces_a_name_in_english() -> None:
    assert _opening_of(("Hello, you're speaking with Sarah.", 2000),
                       language_id="en").detail["name"] is True


def test_the_opening_follows_the_language_of_the_call() -> None:
    opening = _opening_of(("Hello, this is Sarah. How can I help?", 2000), language_id="en")

    assert opening.value == 3


def test_i_am_introduces_a_name_in_english() -> None:
    assert _opening_of(("Hi Samantha, I'm Alice.", 2000), language_id="en").detail["name"]
    assert not _opening_of(("I'm fine, thanks.", 2000), language_id="en").detail["name"]


def test_the_opening_needs_a_vocabulary() -> None:
    assert _opening_of(("Guten Tag.", 1000), language_id=None) is None


def test_the_opening_tempo_is_read_against_the_rest_of_the_call() -> None:
    opening = _opening_of(
        ("Guten Tag hier ist Schmidt womit kann ich Ihnen helfen", 2000),
        ("eins zwei drei vier fünf sechs sieben acht neun zehn "
         "elf zwölf dreizehn vierzehn fünfzehn sechzehn siebzehn achtzehn neunzehn zwanzig", 8000),
    )

    assert opening.detail["pace_ratio"] == pytest.approx(2.0)


def test_a_call_with_one_turn_has_no_tempo_to_compare() -> None:
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
    closing = _closing_of(
        "Ich fasse kurz zusammen: Wir tauschen das Gerät. Ich schicke Ihnen bis Freitag "
        "die Bestätigung.",
        "Danke für Ihren Anruf, auf Wiederhören.",
    )

    assert closing.value == 3
    assert _parts(closing) == (True, True, True)
    assert closing.detail["turns_read"] == 2


def test_the_closing_reads_only_the_last_two_turns() -> None:
    closing = _closing_of(
        "Wir haben also vereinbart, dass Sie das Gerät einschicken.",
        "Ja, genau so.",
        "Tschüss.",
    )

    assert _parts(closing) == (False, False, True)


def test_a_call_too_short_to_have_a_closing_has_none() -> None:
    turns = [Turn(seq=1, persona_text="Guten Tag."),
             Turn(seq=2, user_text="Hallo, auf Wiederhören.", user_speech_ms=1000,
                  user_phonation_ms=1000)]
    assert not [m for m in measure(conversation(turns, "de")) if m.key == "closing"]


def test_a_vague_promise_is_no_agreement() -> None:
    closing = _closing_of("Ich kümmere mich darum.", "Tschüss.")

    assert closing.detail["agreement"] is False


def test_a_question_about_how_is_no_agreement() -> None:
    closing = _closing_of("Und wie machen wir das jetzt?", "Gut.")

    assert closing.detail["agreement"] is False


def test_a_deadline_given_as_a_window_is_an_agreement() -> None:
    for said in (
        "Es sollte innerhalb der nächsten halben Stunde fertig sein.",
        "Das ist in den nächsten zwei Tagen erledigt.",
        "Es dauert nur noch bis zu dem eben genannten Datum.",
    ):
        closing = _closing_of(said, "Tschüss.")
        assert closing.detail["agreement"] is True, said


def test_a_place_is_no_deadline() -> None:
    closing = _closing_of("Das klären wir innerhalb unserer Abteilung.", "Tschüss.")

    assert closing.detail["agreement"] is False


def test_a_greeting_is_no_farewell() -> None:
    closing = _closing_of("Schönen guten Tag nochmal.", "Ja.")

    assert closing.detail["farewell"] is False


def test_the_closing_is_the_same_whoever_rang() -> None:
    said = ("Ich melde mich bis Montag bei Ihnen.", "Einen schönen Tag noch.")

    assert _parts(_closing_of(*said)) == _parts(_closing_of(*said, reverse=True))


def test_the_closing_follows_the_language_of_the_call() -> None:
    closing = _closing_of(
        "Just to recap, I'll send you the new contract by Friday.",
        "Thanks for your time, goodbye.",
        language_id="en",
    )

    assert closing.value == 3


def test_the_closing_needs_a_vocabulary() -> None:
    assert _closing_of("Auf Wiederhören.", "Tschüss.", language_id=None) is None


def test_an_unmeasured_turn_contributes_no_reaction_time() -> None:
    assert [r.gap_ms for r in conversation(_call_with_one_unmeasured_turn()).reactions] == [500]


def test_incomplete_acoustics_suppress_the_metrics_that_depend_on_them() -> None:
    keys = set(_by_key(_call_with_one_unmeasured_turn()))

    assert "talk_share" not in keys
    assert "pace" not in keys
    assert {"word_count", "questions"} <= keys


def test_the_opening_turn_does_not_count_as_a_failed_measurement() -> None:
    assert conversation(_measured_call()).user_acoustics_complete is True


def test_words_without_measured_speech_still_suppress_the_share() -> None:
    turns = [
        Turn(seq=1, persona_text="Guten Tag.", persona_offset_ms=0, persona_end_ms=1_000),
        Turn(seq=2, user_text="Ich habe gesprochen", user_offset_ms=1_500, user_end_ms=3_000),
    ]

    assert "talk_share" not in set(_by_key(turns))


def test_pauses_come_from_the_same_segmentation_as_phonation() -> None:
    turns = _measured_call()
    turns[1].pauses = [Pause(offset_ms=2_000, duration_ms=1_000)]

    values = _by_key(turns)

    assert values["pauses"] == 1.0


# Mean length of runs; runs = pauses inside utterances + utterances. The tests
# pin that arithmetic, which is off by one either way if boundaries are miscounted.


def test_an_uninterrupted_utterance_is_one_run() -> None:
    values = _by_key(_measured_call())

    assert values["run_length"] == _PHONATION_MS / 1_000


def test_a_pause_inside_an_utterance_splits_it_into_two_runs() -> None:
    turns = _measured_call()
    turns[1].pauses = [Pause(offset_ms=2_000, duration_ms=500)]

    values = _by_key(turns)

    assert values["run_length"] == _PHONATION_MS / 2 / 1_000
    # ... while the tempo, which divides by that speaking time, is unmoved.
    assert values["pace"] == _by_key(_measured_call())["pace"]


def test_the_detail_carries_both_terms_of_the_denominator() -> None:
    turns = _measured_call()
    turns[1].pauses = [Pause(offset_ms=2_000, duration_ms=500)]

    detail = {m.key: m.detail for m in measure(conversation(turns))}["run_length"]

    assert detail["utterances"] == 1
    assert detail["pause_count"] == 1
    assert detail["runs"] == 2
    assert detail["phonation_ms"] == _PHONATION_MS


def test_an_unmeasured_turn_suppresses_the_run_length() -> None:
    assert "run_length" not in set(_by_key(_call_with_one_unmeasured_turn()))


def test_a_call_the_user_never_spoke_in_has_no_run_length() -> None:
    turns = [Turn(seq=1, persona_text="Guten Tag.", persona_offset_ms=0, persona_end_ms=1_000)]

    assert "run_length" not in set(_by_key(turns))


def test_the_run_length_carries_no_step_and_no_colour() -> None:
    detail = {m.key: m.detail for m in measure(conversation(_measured_call()))}["run_length"]

    assert "light" not in detail
    assert "step" not in detail


def _call_with_a_barge_in() -> list[Turn]:
    """Carries both ends a real trimmed Turn has; a one-end fixture let a regression through."""
    return [
        Turn(seq=1, persona_text="Guten Tag, ich rufe an wegen der offenen Rechnung ...",
             persona_offset_ms=0, persona_end_ms=3_200, persona_dispatched_end_ms=10_000,
             persona_interrupted=True),
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
    values = _by_key(_call_with_a_barge_in())

    assert values["interruptions"] == 1.0


def test_a_trimmed_reply_the_user_did_not_overlap_is_not_an_interruption() -> None:
    turns = _measured_call()
    turns[1].persona_interrupted = True

    assert _by_key(turns)["interruptions"] == 0.0


def test_a_call_nobody_interrupted_reports_zero_rather_than_nothing() -> None:
    values = _by_key(_measured_call())

    assert values["interruptions"] == 0.0


def test_the_count_carries_its_context_without_dividing_by_it() -> None:
    detail = next(
        m.detail for m in measure(conversation(_call_with_a_barge_in()))
        if m.key == "interruptions"
    )

    assert detail["persona_turns"] == 2
    assert detail["soft_count"] == 0
    assert detail["hard_offsets_ms"] == [3_000]
    assert "interruption_rate" not in {m.key for m in measure(conversation(_measured_call()))}


def test_a_call_with_no_persona_reply_yields_no_interruption_figure() -> None:
    turns = [Turn(seq=1, user_text="Hallo?", user_speech_ms=500, user_phonation_ms=400)]

    assert "interruptions" not in _by_key(turns)


def test_intonation_is_reported_in_semitones() -> None:
    turns = _measured_call()
    turns[1].pitch_hz = [120.0] * 30 + [180.0] * 30

    values = _by_key(turns)

    assert values["intonation"] == pytest.approx(7.02, abs=0.6)


def test_an_unvoiced_call_has_no_pitch_figure() -> None:
    turns = _measured_call()
    turns[1].pitch_hz = [None] * 60

    assert "intonation" not in _by_key(turns)


def test_a_handful_of_voiced_frames_is_not_a_range() -> None:
    turns = _measured_call()
    turns[1].pitch_hz = [120.0, 240.0, 130.0]

    assert "intonation" not in _by_key(turns)


def test_the_curve_carries_the_seams_between_the_users_turns() -> None:
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
    assert "even" in describe_loudness_course(_steady(600))


def test_a_sustained_shift_is_named_with_where_it_happened() -> None:
    described = describe_loudness_course(_with_stretch(shift=10.0, length=60, at=450))

    assert "louder stretch" in described
    assert "in the final third" in described


def test_a_brief_change_is_not_a_stretch() -> None:
    assert "even" in describe_loudness_course(_with_stretch(shift=10.0, length=10, at=450))


def test_a_shift_covering_a_third_of_the_call_is_still_found() -> None:
    described = describe_loudness_course(_with_stretch(shift=-9.0, length=200, at=380))

    assert "quieter stretch" in described


def test_both_directions_are_reported_when_both_happened() -> None:
    curve = _with_stretch(shift=10.0, length=60, at=60)
    for index in range(430, 490):
        value = curve[index]
        assert value is not None
        curve[index] = value - 9.0

    described = describe_loudness_course(curve)

    assert "louder stretch" in described
    assert "quieter stretch" in described


def test_the_description_carries_no_figure_and_no_timestamp() -> None:
    described = describe_loudness_course(_with_stretch(shift=10.0, length=60, at=450))

    assert not any(character.isdigit() for character in described)
    assert "dB" not in described


def test_a_call_with_almost_no_audible_speech_says_so() -> None:
    assert "too little" in describe_loudness_course([None] * 40 + [65.0, 66.0])


CATALOGUE_TS = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "utils" / "metrics.ts"
)


def _catalogue_entries() -> dict[str, str]:
    """Read from the frontend source as text: there is no Node in the pytest run."""
    text = CATALOGUE_TS.read_text(encoding="utf-8")
    body = text.split("const CATALOGUE: Record<MetricKey, MetricDescriptor> = {", 1)[1]
    body = body.split("\n};", 1)[0]
    # Each entry starts at column 2 and runs to the next one, which is what lets
    # a multi-line entry's own fields be read (`derived` below).
    starts = list(re.finditer(r"^  ([a-z_]+):", body, re.MULTILINE))
    entries: dict[str, str] = {}
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(body)
        entries[match.group(1)] = body[match.start():end]
    return entries


def _measured_catalogue_keys() -> set[str]:
    """Catalogue keys of measured metrics; `derived` entries are left out."""
    return {
        key for key, body in _catalogue_entries().items() if "derived: true" not in body
    }


def test_frontend_catalogue_covers_every_metric():
    active = {m.key for m in METRICS if m.active}
    described = _measured_catalogue_keys()

    assert described - active == set(), (
        "frontend/src/utils/metrics.ts describes metrics the backend does not "
        "serve; remove them from CATALOGUE and from MetricKey"
    )
    assert active - described == set(), (
        "frontend/src/utils/metrics.ts is missing metrics the backend serves; "
        "add them to MetricKey and CATALOGUE"
    )
