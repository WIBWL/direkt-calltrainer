"""The Session's statistics, derived from a finished call.

Covers:
  F-24  Redeanteil, and the unit it is a share *of*
  F-36  Sprechtempo, and the unit it is a rate *over*
  F-53  Reaktionszeit: only from Turns whose start was actually measured
  ADR 0047/0048  a Turn's acoustics are measured inline and never load-bearing,
                 so a failed measurement stays visible downstream
  ADR 0051  no figure the user could take for measured when it was not

`conversation()` and `measure()` are pure functions over in-memory Turns: no
database, no audio and no Praat -- the acoustic facts are handed in as the
numbers `analyze()` would have produced.
"""

from backend.feedback.acoustics import Pause
from backend.feedback.metrics import measure
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
