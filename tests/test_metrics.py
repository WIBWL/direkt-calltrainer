"""The Session's statistics, derived from a finished call.

Covers:
  F-24  Redeanteil, and the unit it is a share *of*
  F-36  Sprechtempo, and the unit it is a rate *over*
  F-53  Reaktionszeit: only from Turns whose start was actually measured
  F-37  the loudness curve, and the words the wrap-up gets instead of its
        dB span
  ADR 0047/0048  a Turn's acoustics are measured inline and never load-bearing,
                 so a failed measurement stays visible downstream
  ADR 0051  no figure the user could take for measured when it was not

`conversation()` and `measure()` are pure functions over in-memory Turns: no
database, no audio and no Praat -- the acoustic facts are handed in as the
numbers `analyze()` would have produced.
"""

import pytest

from backend.feedback.acoustics import Pause
from backend.feedback.metrics import describe_loudness_course, measure
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

    # 60 frames at 10 ms thinned to the 100 ms display grid is 6 points.
    assert detail["turn_breaks"] == [6]
    assert len(detail["curve_hz"]) == 12
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
