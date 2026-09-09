"""The four factors read off a pitch contour (F-35).

Constructed contours in Hertz, at the 10 ms grid `acoustics.py` produces: no
audio, no Praat, no database. The point of this file is that each factor
measures the thing it claims to and not one of the others, because that
separation is the whole reason there are four of them instead of one.

The case that matters most is the pair at the top: a wide-but-slow contour and a
narrow-but-lively one. A single range figure calls the first one expressive and
the second one flat, which is backwards for a listener.
"""
import pytest

from backend.api.sessions import _served_detail
from backend.feedback.intonation import (
    BALANCED_MAX_ST,
    LIVELY_MAX_ST,
    MAX_STEP_ST,
    MIN_VOICED_MS_FOR_READING,
    MONOTONE_MAX_ST,
    RANGE_KEY,
    STEP_MS,
    TERMINAL_FLAT_ST,
    VERY_MONOTONE_MAX_ST,
    Ending,
    Liveliness,
    effective_step_ms,
    liveliness,
    liveliness_steps,
    profile,
    semitones,
    thin,
    utterance_breaks,
)


def _steady(hz: float, frames: int) -> tuple[float, ...]:
    return tuple(hz for _ in range(frames))


def _sweep(start: float, end: float, frames: int) -> tuple[float, ...]:
    """A straight glide in semitone space, which is how a voice actually moves."""
    span = semitones(end, start)
    return tuple(start * 2 ** (span / 12 * i / (frames - 1)) for i in range(frames))


def _zigzag(centre: float, depth_st: float, period_frames: int, frames: int) -> tuple[float, ...]:
    """Alternating up and down, `depth_st` peak to peak."""
    out = []
    for i in range(frames):
        high = (i // (period_frames // 2)) % 2 == 0
        out.append(centre * 2 ** (depth_st / 24 * (1 if high else -1)))
    return tuple(out)


# --- Range and movement are different things --------------------------------


def test_a_wide_slow_contour_and_a_narrow_lively_one_differ_in_movement() -> None:
    """The pair this module exists for. Both speakers cover ground; only one of
    them is doing anything with their voice while they speak, and a range
    figure alone cannot tell them apart."""
    drifting = profile(_sweep(100, 160, 400), ())
    lively = profile(_zigzag(120, 4.0, 20, 400), ())

    # The drifter covers more ground ...
    assert drifting.range_st is not None and lively.range_st is not None
    assert drifting.range_st > lively.range_st
    # ... and moves far less while doing it.
    assert drifting.movement_st_per_s is not None
    assert lively.movement_st_per_s is not None
    assert lively.movement_st_per_s > drifting.movement_st_per_s * 5


def test_a_flat_contour_has_no_range_and_no_movement() -> None:
    """A monotone delivery, which must not come out looking varied on either
    factor. No judgement is attached to that (ADR 0051); this pins that the
    measurement follows the signal."""
    flat = profile(_steady(120, 300), ())

    assert flat.range_st == 0.0
    assert flat.movement_st_per_s == 0.0


def test_movement_is_per_second_and_not_per_frame() -> None:
    """So the figure does not change when the analysis grid does. Two contours
    of the same shape at different lengths must read the same."""
    short = profile(_zigzag(120, 4.0, 20, 200), ())
    long = profile(_zigzag(120, 4.0, 20, 800), ())

    assert short.movement_st_per_s == pytest.approx(long.movement_st_per_s, rel=0.05)


def test_a_tracker_jump_is_not_counted_as_movement() -> None:
    """An octave error between neighbouring frames is the tracker changing its
    mind, not a voice: at 10 ms no speaker moves half an octave. Counted, a
    handful of them would dominate the figure."""
    clean = list(_steady(120, 300))
    jumpy = clean[:150] + [240.0] + clean[151:]  # one doubled frame

    assert profile(tuple(jumpy), ()).movement_st_per_s == 0.0
    assert semitones(240, 120) > MAX_STEP_ST  # the jump really is out of range


# --- Terminal contours ------------------------------------------------------


def _falling() -> tuple[float, ...]:
    return _steady(120, 60) + _sweep(120, 95, 40)


def _rising() -> tuple[float, ...]:
    return _steady(120, 60) + _sweep(120, 150, 40)


def test_a_sentence_that_drops_at_the_end_is_read_as_falling() -> None:
    """The conventional close of a statement. Not "good": what it is useful for
    is the mismatch, a speaker who never closes anything."""
    shape = profile(_falling(), (_falling(),))

    assert shape.endings.falling == 1
    assert shape.endings.rising == 0


def test_a_sentence_that_lifts_at_the_end_is_read_as_rising() -> None:
    """Open, questioning, or seeking agreement. Also not a fault by itself."""
    shape = profile(_rising(), (_rising(),))

    assert shape.endings.rising == 1
    assert shape.endings.falling == 0


def test_a_small_final_movement_counts_as_level() -> None:
    """Below the threshold a listener hears wobble, not a direction. Reading
    every twitch as an intention would make the counts meaningless."""
    barely = _steady(120, 60) + _sweep(120, 120 * 2 ** (TERMINAL_FLAT_ST / 24 / 12), 40)

    assert profile(barely, (barely,)).endings.level == 1


def test_endings_are_counted_per_utterance() -> None:
    """Three sentences, three readings. The flat contour of the whole call
    cannot answer this: where one sentence ended is not recoverable from it."""
    shape = profile(_falling() + _rising() + _falling(), (_falling(), _rising(), _falling()))

    assert (shape.endings.falling, shape.endings.rising) == (2, 1)
    assert shape.endings.total == 3


def test_an_utterance_too_short_to_read_is_skipped_rather_than_guessed() -> None:
    """A two-frame "slope" is a guess. Skipped, so the counts stay statements
    about sentences that actually had an ending."""
    assert profile(_steady(120, 300), (_steady(120, 4),)).endings.total == 0


# --- Development across the call --------------------------------------------


def test_the_first_and_last_third_are_reported_separately() -> None:
    """A change within one speaker needs no external reference, which is what
    makes it sayable at all under ADR 0051. Here the voice flattens out."""
    lively_then_flat = _zigzag(120, 6.0, 20, 300) + _steady(120, 300)

    shape = profile(lively_then_flat, ())

    assert shape.range_first_st is not None and shape.range_last_st is not None
    assert shape.range_first_st > shape.range_last_st + 2


def test_the_thirds_are_thirds_of_speech_and_not_of_the_clock() -> None:
    """A long silence in the middle must not swallow the second third. Voiced
    frames are what is divided, so a pause belongs to neither side."""
    talk = _zigzag(120, 6.0, 20, 200)
    silence = tuple([None] * 2_000)

    shape = profile(talk + silence + talk, ())

    assert shape.range_first_st is not None and shape.range_last_st is not None
    assert shape.range_first_st == pytest.approx(shape.range_last_st, abs=1.0)


# --- What is refused --------------------------------------------------------


def test_a_contour_with_too_few_voiced_frames_yields_nothing() -> None:
    """Whispering, or a Turn Praat found almost no voicing in. Every factor is
    a shape, and a shape needs points; a figure from five frames would be a
    number with no measurement behind it."""
    shape = profile(_steady(120, 5), ())

    assert shape.range_st is None
    assert shape.movement_st_per_s is None
    assert shape.median_hz is None


def test_unvoiced_frames_never_enter_a_figure() -> None:
    """They are consonants, breaths and pauses. Counted as zero they would drag
    every factor towards a value nobody produced."""
    with_gaps = _steady(120, 100) + (None,) * 50 + _steady(120, 100)

    shape = profile(with_gaps, ())

    assert shape.median_hz == 120.0
    assert shape.range_st == 0.0


# --- The display curve ------------------------------------------------------


def test_thinning_keeps_the_shape_and_the_gaps() -> None:
    """Three minutes at 10 ms is eighteen thousand points and no chart resolves
    them. What the thinned curve must not do is invent voicing across a pause."""
    contour = _steady(120, 100) + (None,) * 100 + _steady(150, 100)

    thinned = thin(contour, 100)

    assert len(thinned) == pytest.approx(30, abs=1)  # 300 frames at 10 ms -> 100 ms
    assert thinned[0] == 120.0
    assert thinned[-1] == 150.0
    assert None in thinned


def test_thinning_takes_the_median_of_each_window_not_a_sample() -> None:
    """One stray frame must not become a visible spike in the drawing."""
    contour = list(_steady(120, 100))
    contour[45] = 400.0

    assert 400.0 not in thin(tuple(contour), 100)


def test_the_grid_constant_matches_the_analysis() -> None:
    """The movement figure divides by it. If this drifts from acoustics.py, the
    semitones per second silently change by the same factor."""
    assert STEP_MS == 10


def test_an_ending_is_read_from_voiced_frames_only() -> None:
    """Utterances end in consonants and breath. Reading the last frames of the
    recording would read the silence after the sentence."""
    falling_then_silence = _falling() + (None,) * 50

    assert profile(falling_then_silence, (falling_then_silence,)).endings.falling == 1


def test_ending_values_are_the_documented_vocabulary() -> None:
    """The frontend words these; a fourth value would render as nothing."""
    assert {e.value for e in Ending} == {"falling", "rising", "level"}


# --- The five-step reading of the range -------------------------------------
# The one part of this module that judges. These tests pin the boundaries, not
# because the numbers are established -- they are not -- but so that changing
# one is a deliberate act with a test to update.


def test_each_step_of_the_scale_is_reachable() -> None:
    """A scale with an unreachable step is a scale with fewer steps. Each
    boundary is taken from just below and just above."""
    assert liveliness(0.5) is Liveliness.VERY_MONOTONE
    assert liveliness(VERY_MONOTONE_MAX_ST - 0.1) is Liveliness.VERY_MONOTONE
    assert liveliness(VERY_MONOTONE_MAX_ST) is Liveliness.MONOTONE
    assert liveliness(MONOTONE_MAX_ST - 0.1) is Liveliness.MONOTONE
    assert liveliness(MONOTONE_MAX_ST) is Liveliness.BALANCED
    assert liveliness(BALANCED_MAX_ST - 0.1) is Liveliness.BALANCED
    assert liveliness(BALANCED_MAX_ST) is Liveliness.LIVELY
    assert liveliness(LIVELY_MAX_ST - 0.1) is Liveliness.LIVELY
    assert liveliness(LIVELY_MAX_ST) is Liveliness.EXAGGERATED


def test_an_unmeasured_range_gets_no_step() -> None:
    """Whispering, or a call too short to have a shape. "stark monoton" would
    be a verdict on a measurement that was never taken."""
    assert liveliness(None) is None


def test_a_monotone_contour_reads_as_monotone_and_a_lively_one_as_lively() -> None:
    """End to end over the measurement, not over the thresholds: a voice that
    barely moves and one that works in every phrase must not land on the same
    step, which is the whole point of the feature."""
    flat = profile(_steady(120, 400), ())
    lively = profile(_zigzag(120, 13.0, 40, 400), ())

    assert flat.range_st is not None and lively.range_st is not None
    assert liveliness(flat.range_st) is Liveliness.VERY_MONOTONE
    assert liveliness(lively.range_st) is Liveliness.LIVELY


def test_the_scale_is_built_from_the_thresholds_and_carries_no_colour() -> None:
    """The legend and the logic come from the same constants, so a
    recalibration reaches both. No colour: the scale is uncomfortable at both
    ends, so there is no direction for one to point in."""
    steps = liveliness_steps()

    assert [s["step"] for s in steps] == [step.value for step in Liveliness]
    assert [s["label"] for s in steps] == [
        "stark monoton", "monoton", "ausgewogen", "lebendig", "überzeichnet",
    ]
    assert steps[0]["range"] == "unter 4 Halbtönen"
    assert steps[2]["range"] == "7 bis 12 Halbtöne"
    assert steps[4]["range"] == "über 18 Halbtönen"
    assert all(s["light"] is None for s in steps)


def test_the_step_is_derived_when_the_session_is_read() -> None:
    """Not stored with the Measurement, on purpose.

    The figure is a measurement and is written once; the step is a judgement on
    thresholds nothing has validated, so it is computed on every read from the
    stored figure. That is what lets a recalibration reach trainings recorded
    months ago, whose audio is long gone (ADR 0048) and which therefore could
    never be measured again.
    """
    served = _served_detail(RANGE_KEY, 9.0, {"median_hz": 120.0})

    assert served == {
        "median_hz": 120.0,
        "liveliness": "balanced",
        "liveliness_label": "ausgewogen",
    }


def test_serving_leaves_a_detail_that_was_never_measured_alone() -> None:
    """A Session stored before the pitch curve existed carries no detail at
    all. There is nothing to read a step off, and inventing one would put a
    word on a training that was never measured."""
    assert _served_detail(RANGE_KEY, 9.0, None) is None


# --- Where one utterance ends and the next begins ---------------------------


def test_utterance_seams_land_on_the_thinned_curve() -> None:
    """The curve is speaking time: the Persona's turns are not in it, so a seam
    is the only thing that says two stretches were not one breath."""
    utterances = (_steady(120, 250), _steady(130, 250), _steady(140, 100))

    marks = utterance_breaks(utterances, 100)

    # 250 frames at 10 ms thinned to 100 ms is 25 points, then 25 more.
    assert marks == [25, 50]


def test_a_call_of_one_utterance_has_no_seams() -> None:
    """Nothing to mark, and a mark at the end of the last utterance would be a
    line at the right edge with nothing behind it."""
    assert not utterance_breaks((_steady(120, 300),), 100)


def test_two_seams_inside_one_window_are_marked_once() -> None:
    """A very short utterance puts two seams in the same 100 ms window. One
    line, not two on top of each other: the second would be invisible and would
    still be in the count the caption states."""
    barely_spoke = (_steady(120, 105), _steady(130, 4), _steady(140, 300))

    assert utterance_breaks(barely_spoke, 100) == [10]


def test_the_stated_grid_is_the_one_thinning_produced() -> None:
    """Thinning works in whole 10 ms frames, so a request for 25 ms yields
    20 ms. Everything that reads the curve -- the drawing's time axis, the seam
    indices -- has to use what came out, or the picture claims a duration the
    curve does not have."""
    assert effective_step_ms(50) == 50
    assert effective_step_ms(25) == 20
    assert len(thin(_steady(120, 100), 25)) == pytest.approx(50, abs=1)


def test_the_band_is_measured_at_both_ends_and_not_assumed_symmetric() -> None:
    """The drawing puts a band behind the contour. Taken as the range halved
    either side of the median, that band is a guess about the shape of the
    distribution; a voice that reaches further up than down would be drawn with
    its band in the wrong place."""
    # Twice as much room above the median as below it.
    lopsided = _steady(120, 200) + _sweep(120, 170, 100) + _sweep(120, 109, 100)

    shape = profile(lopsided, ())

    assert shape.band_low_st is not None and shape.band_high_st is not None
    assert shape.band_high_st > abs(shape.band_low_st)
    # ... and the two ends still add up to the figure the Kennzahl reports.
    assert shape.band_high_st - shape.band_low_st == pytest.approx(shape.range_st, abs=0.05)


def test_movement_is_not_counted_across_the_seam_between_two_utterances() -> None:
    """The call's contour is the user's utterances laid end to end with the
    Persona's turns taken out. The last frame of one and the first frame of the
    next are neighbours in that array and a minute apart in the call; a step
    between them is movement the voice never made."""
    # A step just under MAX_STEP_ST, so it is not thrown out as an octave error
    # first and the seam rule is what this actually tests.
    low = _steady(110, 200)
    high = _steady(155, 200)
    assert semitones(155, 110) < MAX_STEP_ST

    seamless = profile(low + high, (low, high))
    as_one_stretch = profile(low + high, ())

    assert seamless.movement_st_per_s == 0.0
    assert as_one_stretch.movement_st_per_s is not None
    assert as_one_stretch.movement_st_per_s > 0


def test_a_step_is_read_only_from_enough_voiced_speech() -> None:
    """Five steps on two seconds of humming would be a verdict on nothing. The
    figure is still reported -- a spread is a spread -- but it carries no word."""
    assert liveliness(9.0, MIN_VOICED_MS_FOR_READING) is Liveliness.BALANCED
    assert liveliness(9.0, MIN_VOICED_MS_FOR_READING - 1) is None
    assert liveliness(9.0, None) is Liveliness.BALANCED  # not recorded: no reason to withhold
