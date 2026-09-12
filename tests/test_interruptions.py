"""Overlapping speech, classified (F-51, focus goal C1 "Aktives Zuhören").

The rules are ordered and the first match wins, so most of this file is about
the order rather than about any single rule. One property carries the rest: a
backchannel must never be counted as an interruption. Getting that wrong would
mean the trainer punishes the thing it is trying to teach, and it would do so
silently, because the figure would still look plausible.

Constructed timelines throughout: two speakers, milliseconds, no database and
no audio. The thresholds are imported rather than written out, so the tests
follow a recalibration instead of pinning yesterday's numbers -- except where a
test is explicitly about the value of a constant.
"""
from backend.feedback.interruptions import (
    BACKCHANNEL_MAX_MS,
    GREEN_MAX_COUNT,
    TERMINAL_WINDOW_MS,
    YELLOW_MAX_COUNT,
    YIELD_WINDOW_MS,
    Kind,
    Segment,
    TrafficLight,
    classify,
    light_steps,
)


def _persona(offset: int, duration: int, interrupted: bool = False) -> Segment:
    return Segment("persona", offset, duration, interrupted)


def _user(offset: int, duration: int = 5_000) -> Segment:
    return Segment("user", offset, duration)


def _kinds(*timeline: Segment) -> list[Kind]:
    return [event.kind for event in classify(tuple(timeline)).events]


# --- Finding the candidates -------------------------------------------------


def test_a_reply_that_waited_for_the_persona_is_no_event_at_all() -> None:
    """The ordinary case, and by far the most common one: the user starts after
    the Persona has finished. Nothing to classify."""
    assert _kinds(_persona(0, 4_000), _user(4_500)) == []


def test_starting_before_the_persona_did_is_no_overlap_either() -> None:
    """A user segment that begins ahead of the Persona line is the Persona
    answering, not the user cutting in."""
    assert _kinds(_user(0, 2_000), _persona(2_500, 3_000)) == []


def test_the_overlapped_line_is_the_one_still_running() -> None:
    """Persona windows are modelled from dispatched audio and can abut. The
    candidate is the line the user started inside of, not the first one."""
    events = classify((
        _persona(0, 2_000),
        _persona(2_000, 6_000, interrupted=True),
        _user(3_000),
    )).events

    assert len(events) == 1
    assert events[0].remaining_ms == 5_000  # measured against the second line


# --- Rule 1: backchannels ---------------------------------------------------


def test_a_short_signal_that_costs_the_persona_nothing_is_a_backchannel() -> None:
    """The rule this file exists for. "Mhm" while the other side keeps talking
    is listening, and counting it would punish exactly the behaviour the goal
    asks for."""
    short = BACKCHANNEL_MAX_MS - 1

    assert _kinds(_persona(0, 8_000), _user(2_000, short)) == [Kind.BACKCHANNEL]


def test_a_backchannel_wins_over_every_other_rule() -> None:
    """Deep inside the line, far from its end: every later rule would call this
    an interruption. The order is what prevents that."""
    short = BACKCHANNEL_MAX_MS - 1

    assert _kinds(_persona(0, 20_000), _user(5_000, short)) == [Kind.BACKCHANNEL]


def test_a_short_utterance_that_did_cut_the_persona_off_is_not_a_backchannel() -> None:
    """The second half of the rule. If the reply was trimmed, the Persona lost
    words over it, which is not what a listening signal does."""
    short = BACKCHANNEL_MAX_MS - 1
    timeline = (_persona(0, 20_000, interrupted=True), _user(5_000, short))

    assert _kinds(*timeline) == [Kind.HARD]


# --- Rule 2: terminal overlap -----------------------------------------------


def test_starting_as_the_line_ends_is_ordinary_turn_taking() -> None:
    """Speaker changes across languages cluster around a fifth of a second,
    with overlap either side of zero (Stivers et al. 2009). Inside that window
    nobody was interrupted."""
    persona = _persona(0, 4_000)
    barely_early = persona.end_ms - (TERMINAL_WINDOW_MS - 50)

    assert _kinds(persona, _user(barely_early)) == [Kind.TERMINAL]


def test_the_terminal_window_is_two_hundred_milliseconds() -> None:
    """The one threshold here with a source behind it, pinned so that changing
    it is a decision rather than an edit."""
    assert TERMINAL_WINDOW_MS == 200


def test_a_terminal_overlap_stays_terminal_even_if_the_reply_was_trimmed() -> None:
    """A trim with a hair's worth of audio left is a rounding artefact of the
    modelled window, not somebody being cut off."""
    persona = _persona(0, 4_000, interrupted=True)

    assert _kinds(persona, _user(persona.end_ms - 100)) == [Kind.TERMINAL]


# --- Rules 3 and 4: hard and soft -------------------------------------------


def test_cutting_a_line_off_with_seconds_left_is_a_hard_interruption() -> None:
    """The event the focus goal is actually about: the Persona had more to say
    and did not get to say it."""
    assert _kinds(_persona(0, 10_000, interrupted=True), _user(3_000)) == [Kind.HARD]


def test_an_overlap_that_cost_the_persona_nothing_is_soft() -> None:
    """The user started well inside the line, but everything the Persona had to
    say was heard. Worth reporting, not worth counting."""
    assert _kinds(_persona(0, 10_000), _user(3_000)) == [Kind.SOFT]


def test_a_trim_with_less_than_the_yield_window_left_is_not_counted_hard() -> None:
    """Between the terminal window and the yield window: the reply was cut, but
    by so little that calling it an interruption would overstate it."""
    persona = _persona(0, 4_000, interrupted=True)
    late = persona.end_ms - (YIELD_WINDOW_MS - 100)

    assert _kinds(persona, _user(late)) == [Kind.SOFT]


# --- The Session figure -----------------------------------------------------


def test_only_hard_interruptions_are_counted() -> None:
    """Soft overlaps and backchannels are in the report and out of the figure.
    A count that included them would rise when somebody listened attentively."""
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
    """Zero is a measurement, not a missing one: it says every reply was heard
    out."""
    report = classify((_persona(0, 4_000), _user(5_000)))

    assert not report.hard
    assert report.light is TrafficLight.GREEN


# --- The provisional traffic light ------------------------------------------
# Two invented thresholds, and the tests say so. They pin the arithmetic, not
# the claim that these are the right numbers -- nothing has established that.


def test_an_overlap_that_cost_nothing_leaves_the_light_green() -> None:
    """Only hard interruptions move it. A call full of attentive overlaps must
    not read as a call full of interruptions."""
    report = classify((_persona(0, 10_000), _user(2_000)))  # one soft overlap

    assert report.light is TrafficLight.GREEN


def test_the_light_turns_at_the_configured_counts() -> None:
    """n hard interruptions, either side of each boundary.

    On a count and not on a share of Persona turns: dividing was tried and, at
    the length these calls actually run, put a single interruption on the top
    step. The call length now travels as context instead of into the figure.
    """
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


# --- Context that stays beside the figure ------------------------------------


def test_the_report_carries_the_call_length_without_dividing_by_it() -> None:
    """The count is per call, so how long that call was is what lets a reader
    weigh it. It is context and not a denominator: dividing was tried and put a
    single interruption on the top step of a short call."""
    report = classify((_persona(0, 10_000, interrupted=True), _user(2_000, 8_000)))

    assert report.call_ms == 10_000
    assert report.light is TrafficLight.YELLOW  # one interruption, whatever the length


def test_backchannels_are_reported_and_never_offset_against_the_count() -> None:
    """Listening is the other half of this goal. A figure that only counted the
    failures would describe an attentive call and an absent one identically --
    but the signals must not buy anything off either, which would invent a
    trade nothing supports."""
    report = classify((
        _persona(0, 20_000, interrupted=True), _user(2_000),           # hard
        _persona(40_000, 20_000), _user(42_000, 500),                  # backchannel
        _persona(70_000, 20_000), _user(72_000, 500),                  # backchannel
    ))

    assert len(report.backchannels) == 2
    assert len(report.hard) == 1
    assert report.light is TrafficLight.YELLOW  # unchanged by the two signals


def test_the_light_steps_are_built_from_the_thresholds() -> None:
    """The legend and the logic come from the same constants, so a
    recalibration reaches both. A boundary the user cannot see is a judgement
    they cannot argue with."""
    steps = light_steps()

    assert [s["light"] for s in steps] == ["green", "yellow", "red"]
    assert steps[0]["range"] == "0"
    assert steps[1]["range"] == "1 bis 2"
    assert steps[2]["range"] == "ab 3"
