"""Overlap classification; first rule wins, backchannels are never interruptions (F-51)."""
from shared.feedback.calls import timeline
from shared.turn import Turn
from shared.feedback.interruptions import (
    BACKCHANNEL_MAX_MS,
    GREEN_MAX_COUNT,
    TERMINAL_WINDOW_MS,
    YELLOW_MAX_COUNT,
    YIELD_WINDOW_MS,
    Kind,
    Segment,
    TrafficLight,
    classify,
    finding_description,
    light_steps,
)


def _persona(offset: int, duration: int, interrupted: bool = False) -> Segment:
    """`duration` is the dispatched length; an interrupted one is heard for a third of it."""
    if not interrupted:
        return Segment("persona", offset, duration)
    return Segment("persona", offset, max(1, duration // 3),
                   interrupted=True, dispatched_ms=duration)


def _user(offset: int, duration: int = 5_000) -> Segment:
    return Segment("user", offset, duration)


def _kinds(*timeline: Segment) -> list[Kind]:
    return [event.kind for event in classify(tuple(timeline)).events]


def test_a_reply_that_waited_for_the_persona_is_no_event_at_all() -> None:
    assert _kinds(_persona(0, 4_000), _user(4_500)) == []


def test_starting_before_the_persona_did_is_no_overlap_either() -> None:
    assert _kinds(_user(0, 2_000), _persona(2_500, 3_000)) == []


def test_the_overlapped_line_is_the_one_still_running() -> None:
    events = classify((
        _persona(0, 2_000),
        _persona(2_000, 6_000, interrupted=True),
        _user(3_000),
    )).events

    assert len(events) == 1
    assert events[0].remaining_ms == 5_000  # measured against the second line


def test_a_short_signal_that_costs_the_persona_nothing_is_a_backchannel() -> None:
    short = BACKCHANNEL_MAX_MS - 1

    assert _kinds(_persona(0, 8_000), _user(2_000, short)) == [Kind.BACKCHANNEL]


def test_a_backchannel_wins_over_every_other_rule() -> None:
    short = BACKCHANNEL_MAX_MS - 1

    assert _kinds(_persona(0, 20_000), _user(5_000, short)) == [Kind.BACKCHANNEL]


def test_a_short_utterance_that_did_cut_the_persona_off_is_not_a_backchannel() -> None:
    short = BACKCHANNEL_MAX_MS - 1
    timeline = (_persona(0, 20_000, interrupted=True), _user(5_000, short))

    assert _kinds(*timeline) == [Kind.HARD]


def test_starting_as_the_line_ends_is_ordinary_turn_taking() -> None:
    persona = _persona(0, 4_000)
    barely_early = persona.end_ms - (TERMINAL_WINDOW_MS - 50)

    assert _kinds(persona, _user(barely_early)) == [Kind.TERMINAL]


def test_the_terminal_window_is_two_hundred_milliseconds() -> None:
    assert TERMINAL_WINDOW_MS == 200


def test_a_terminal_overlap_stays_terminal_even_if_the_reply_was_trimmed() -> None:
    persona = _persona(0, 4_000, interrupted=True)

    # Off the dispatched end: `end_ms` on a trimmed segment is the cut itself.
    assert _kinds(persona, _user(persona.dispatched_end_ms - 100)) == [Kind.TERMINAL]


def test_cutting_a_line_off_with_seconds_left_is_a_hard_interruption() -> None:
    assert _kinds(_persona(0, 10_000, interrupted=True), _user(3_000)) == [Kind.HARD]


def test_an_overlap_that_cost_the_persona_nothing_is_soft() -> None:
    assert _kinds(_persona(0, 10_000), _user(3_000)) == [Kind.SOFT]


def test_a_trim_with_less_than_the_yield_window_left_is_not_counted_hard() -> None:
    persona = _persona(0, 4_000, interrupted=True)
    late = persona.dispatched_end_ms - (YIELD_WINDOW_MS - 100)

    assert _kinds(persona, _user(late)) == [Kind.SOFT]


def test_only_hard_interruptions_are_counted() -> None:
    report = classify((
        _persona(0, 10_000, interrupted=True), _user(2_000),          # hard
        _persona(20_000, 10_000), _user(22_000),                      # soft
        _persona(40_000, 10_000), _user(42_000, 500),                 # backchannel
        _persona(60_000, 4_000), _user(63_950),                       # terminal
    ))

    assert len(report.hard) == 1
    assert len(report.soft) == 1
    assert report.persona_turns == 4


def test_a_call_the_user_never_cut_into_counts_zero() -> None:
    report = classify((_persona(0, 4_000), _user(5_000)))

    assert not report.hard
    assert report.light is TrafficLight.GREEN


# Two invented thresholds, and the tests say so. They pin the arithmetic, not
# the claim that these are the right numbers -- nothing has established that.


def test_an_overlap_that_cost_nothing_leaves_the_light_green() -> None:
    report = classify((_persona(0, 10_000), _user(2_000)))  # one soft overlap

    assert report.light is TrafficLight.GREEN


def test_the_light_turns_at_the_configured_counts() -> None:
    def light_for(hard: int) -> TrafficLight:
        timeline: list[Segment] = []
        for index in range(hard):
            at = 20_000 * index
            timeline.append(_persona(at, 10_000, interrupted=True))
            timeline.append(_user(at + 2_000))
        return classify(tuple(timeline)).light

    assert GREEN_MAX_COUNT == 0 and YELLOW_MAX_COUNT == 2  # what these turn on
    assert light_for(0) is TrafficLight.GREEN
    assert light_for(2) is TrafficLight.YELLOW
    assert light_for(3) is TrafficLight.RED


def test_the_report_carries_the_call_length_without_dividing_by_it() -> None:
    report = classify((_persona(0, 10_000, interrupted=True), _user(2_000, 8_000)))

    assert report.call_ms == 10_000
    assert report.light is TrafficLight.YELLOW  # one interruption, whatever the length


def test_backchannels_are_reported_and_never_offset_against_the_count() -> None:
    report = classify((
        _persona(0, 20_000, interrupted=True), _user(2_000),           # hard
        _persona(40_000, 20_000), _user(42_000, 500),                  # backchannel
        _persona(70_000, 20_000), _user(72_000, 500),                  # backchannel
    ))

    assert len(report.backchannels) == 2
    assert len(report.hard) == 1
    assert report.light is TrafficLight.YELLOW  # unchanged by the two signals


def test_the_light_steps_are_built_from_the_thresholds() -> None:
    steps = light_steps()

    assert [s["light"] for s in steps] == ["green", "yellow", "red"]
    assert steps[0]["range"] == "0"
    assert steps[1]["range"] == "1 bis 2"
    assert steps[2]["range"] == "ab 3"


# Hand-built Segments cannot notice when `calls.timeline` changes meaning.

def test_a_trimmed_reply_is_measured_against_the_audio_that_was_sent() -> None:
    turns = [
        Turn(
            seq=1,
            persona_text="Guten Tag, ich rufe an wegen der offenen Rechnung",
            persona_offset_ms=0,
            # 12 s dispatched, 3.4 s of it played before the cut landed.
            persona_end_ms=3_400,
            persona_dispatched_end_ms=12_000,
            persona_interrupted=True,
        ),
        Turn(
            seq=2,
            user_text="Moment, das stimmt so nicht",
            user_offset_ms=3_000,
            user_end_ms=6_000,
            user_speech_ms=3_000,
        ),
    ]

    report = classify(timeline(turns))

    assert len(report.events) == 1
    event = report.events[0]
    assert event.remaining_ms == 9_000, "12 s of audio, cut into at 3 s"
    assert event.kind is Kind.HARD
    assert "9.0 Sekunden" in finding_description(event)


def test_the_heard_part_is_still_what_the_segment_lasts() -> None:
    turns = [
        Turn(
            seq=1,
            persona_text="Guten Tag",
            persona_offset_ms=0,
            persona_end_ms=3_400,
            persona_dispatched_end_ms=12_000,
            persona_interrupted=True,
        ),
    ]

    (segment,) = timeline(turns)

    assert segment.duration_ms == 3_400
    assert segment.end_ms == 3_400
    assert segment.dispatched_end_ms == 12_000


def test_a_turn_that_knows_only_one_end_reads_it_as_both() -> None:
    segment = Segment("persona", 0, 10_000, interrupted=True)

    assert segment.dispatched_end_ms == segment.end_ms == 10_000


def test_a_cut_reported_slightly_early_is_still_found() -> None:
    # 12 s dispatched, playback stopped at 2.9 s, the user's start derived as 3 s.
    cut_early = Segment("persona", 0, 2_900, interrupted=True, dispatched_ms=12_000)

    assert _kinds(cut_early, _user(3_000)) == [Kind.HARD]
