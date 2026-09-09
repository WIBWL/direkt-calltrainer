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

from backend.feedback.intonation import (
    MAX_STEP_ST,
    STEP_MS,
    TERMINAL_FLAT_ST,
    Ending,
    profile,
    semitones,
    thin,
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
