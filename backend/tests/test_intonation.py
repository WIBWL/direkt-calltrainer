"""The pitch figures from constructed contours (F-35, ADR 0077)."""
from dataclasses import fields
from pathlib import Path

import pytest

from shared.feedback.intonation import (
    GLISSANDO_ST_S2,
    LABELS,
    LIGHTS,
    MAX_STEP_ST,
    MIN_TERMINAL_FRAMES,
    MIN_VOICED_MS_FOR_READING,
    PVQ_LIVELY_MAX,
    PVQ_MONOTONE_MAX,
    PVQ_WINDOW_MS,
    RANGE_KEY,
    STEP_MS,
    TERMINAL_FLAT_ST,
    TERMINAL_WINDOW_MS,
    Endings,
    Liveliness,
    effective_step_ms,
    liveliness,
    liveliness_steps,
    profile,
    semitones,
    thin,
    utterance_breaks,
)
from backend.feedback.readings import served_detail


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


def test_a_wide_slow_contour_and_a_narrow_lively_one_differ_in_movement() -> None:
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
    flat = profile(_steady(120, 300), ())

    assert flat.range_st == 0.0
    assert flat.movement_st_per_s == 0.0


def test_movement_is_per_second_and_not_per_frame() -> None:
    short = profile(_zigzag(120, 4.0, 20, 200), ())
    long = profile(_zigzag(120, 4.0, 20, 800), ())

    assert short.movement_st_per_s == pytest.approx(long.movement_st_per_s, rel=0.05)


def test_a_tracker_jump_is_not_counted_as_movement() -> None:
    clean = list(_steady(120, 300))
    jumpy = clean[:150] + [240.0] + clean[151:]  # one doubled frame

    assert profile(tuple(jumpy), ()).movement_st_per_s == 0.0
    assert semitones(240, 120) > MAX_STEP_ST  # the jump really is out of range


def _falling() -> tuple[float, ...]:
    return _steady(120, 60) + _sweep(120, 95, 40)


def _rising() -> tuple[float, ...]:
    return _steady(120, 60) + _sweep(120, 150, 40)


def test_a_sentence_that_drops_at_the_end_is_read_as_falling() -> None:
    shape = profile(_falling(), (_falling(),))

    assert shape.endings.falling == 1
    assert shape.endings.rising == 0


def test_a_sentence_that_lifts_at_the_end_is_read_as_rising() -> None:
    shape = profile(_rising(), (_rising(),))

    assert shape.endings.rising == 1
    assert shape.endings.falling == 0


def test_a_small_final_movement_counts_as_level() -> None:
    half_of_it = 120 * 2 ** (TERMINAL_FLAT_ST / 2 / 12)
    barely = _steady(120, 60) + _sweep(120, half_of_it, 40)

    assert profile(barely, (barely,)).endings.level == 1


def test_a_movement_over_the_threshold_is_a_direction() -> None:
    clearly = _steady(120, 60) + _sweep(120, 120 * 2 ** (2 * TERMINAL_FLAT_ST / 12), 40)

    assert profile(clearly, (clearly,)).endings.rising == 1


def test_a_short_utterance_is_judged_against_its_own_window() -> None:
    # The call is long enough to be read at all; the *utterance* is the short
    # one, which is what the ending is taken from.
    call = _steady(120, 100)
    one_semitone_down = _sweep(120, 120 * 2 ** (-1.0 / 12), MIN_TERMINAL_FRAMES)

    shape = profile(call, (one_semitone_down,))

    assert shape.endings.level == 1, "1 ST across 70 ms is not a heard movement"
    assert shape.endings.falling == 0

    # Six semitones across the same 70 ms is over that window's own floor.
    six_down = _sweep(120, 120 * 2 ** (-6.0 / 12), MIN_TERMINAL_FRAMES)

    assert profile(call, (six_down,)).endings.falling == 1


def test_endings_are_counted_per_utterance() -> None:
    shape = profile(_falling() + _rising() + _falling(), (_falling(), _rising(), _falling()))

    assert (shape.endings.falling, shape.endings.rising) == (2, 1)
    assert shape.endings.total == 3


def test_an_utterance_too_short_to_read_is_skipped_rather_than_guessed() -> None:
    assert profile(_steady(120, 300), (_steady(120, 4),)).endings.total == 0


def test_the_first_and_last_third_are_reported_separately() -> None:
    lively_then_flat = _zigzag(120, 6.0, 20, 300) + _steady(120, 300)

    shape = profile(lively_then_flat, ())

    assert shape.range_first_st is not None and shape.range_last_st is not None
    assert shape.range_first_st > shape.range_last_st + 2


def test_the_thirds_are_thirds_of_speech_and_not_of_the_clock() -> None:
    talk = _zigzag(120, 6.0, 20, 200)
    silence = tuple([None] * 2_000)

    shape = profile(talk + silence + talk, ())

    assert shape.range_first_st is not None and shape.range_last_st is not None
    assert shape.range_first_st == pytest.approx(shape.range_last_st, abs=1.0)


def test_a_contour_with_too_few_voiced_frames_yields_nothing() -> None:
    shape = profile(_steady(120, 5), ())

    assert shape.range_st is None
    assert shape.movement_st_per_s is None
    assert shape.median_hz is None


def test_unvoiced_frames_never_enter_a_figure() -> None:
    with_gaps = _steady(120, 100) + (None,) * 50 + _steady(120, 100)

    shape = profile(with_gaps, ())

    assert shape.median_hz == 120.0
    assert shape.range_st == 0.0


def test_thinning_keeps_the_shape_and_the_gaps() -> None:
    contour = _steady(120, 100) + (None,) * 100 + _steady(150, 100)

    thinned = thin(contour, 100)

    assert len(thinned) == pytest.approx(30, abs=1)  # 300 frames at 10 ms -> 100 ms
    assert thinned[0] == 120.0
    assert thinned[-1] == 150.0
    assert None in thinned


def test_thinning_takes_the_median_of_each_window_not_a_sample() -> None:
    contour = list(_steady(120, 100))
    contour[45] = 400.0

    assert 400.0 not in thin(tuple(contour), 100)


def test_the_grid_constant_matches_the_analysis() -> None:
    from shared.feedback import acoustics  # pylint: disable=import-outside-toplevel

    assert STEP_MS == round(acoustics._PITCH_STEP_S * 1000)  # pylint: disable=protected-access


def test_an_ending_is_read_from_voiced_frames_only() -> None:
    falling_then_silence = _falling() + (None,) * 50

    assert profile(falling_then_silence, (falling_then_silence,)).endings.falling == 1


def test_the_endings_the_frontend_reads_are_the_ones_measured() -> None:
    page = (
        Path(__file__).resolve().parents[2] /
        "frontend" / "src" / "components" / "IntonationReading.tsx"
    ).read_text(encoding="utf-8")
    body = page.split("interface Endings {", 1)[1].split("}", 1)[0]
    read = {line.strip().split(":", 1)[0] for line in body.splitlines() if ":" in line}

    assert {field.name for field in fields(Endings)} == read == {"falling", "rising", "level"}


# Hincks (2005)'s PVQ: the only figure here with a published boundary.


def test_a_flat_voice_and_a_moving_one_differ_in_the_quotient() -> None:
    flat = profile(_steady(120, 400), ())
    moving = profile(_zigzag(120, 13.0, 40, 400), ())

    assert flat.pvq == 0.0
    assert moving.pvq is not None and moving.pvq > PVQ_LIVELY_MAX


def test_the_quotient_is_measured_per_window_and_not_over_the_whole_call() -> None:
    per_window = PVQ_WINDOW_MS // STEP_MS
    two_registers = _steady(110, per_window) + _steady(190, per_window)

    shape = profile(two_registers, ())

    assert shape.pvq_windows == 2
    assert shape.pvq == 0.0  # flat inside each window, however far apart they sit
    # ... while the range, which is not windowed, sees the whole spread.
    assert shape.range_st is not None and shape.range_st > 8


def test_a_window_that_is_nearly_all_unvoiced_is_skipped() -> None:
    per_window = PVQ_WINDOW_MS // STEP_MS
    good = _zigzag(120, 6.0, 20, per_window)
    mostly_silent = _steady(120, 50) + (None,) * (per_window - 50)

    assert profile(good + mostly_silent, ()).pvq_windows == 1


def test_a_trailing_part_window_is_dropped_rather_than_averaged_in() -> None:
    per_window = PVQ_WINDOW_MS // STEP_MS

    shape = profile(_zigzag(120, 6.0, 20, per_window + 400), ())

    assert shape.pvq_windows == 1


def test_a_call_too_short_for_one_window_is_still_measured() -> None:
    shape = profile(_zigzag(120, 6.0, 20, 400), ())

    assert shape.pvq is not None
    assert shape.pvq_windows == 1


# The boundaries are pinned so that changing one is deliberate, not because they
# are established for this population (ADR 0077).


def test_each_step_of_the_scale_is_reachable() -> None:
    assert liveliness(0.0) is Liveliness.MONOTONE
    assert liveliness(PVQ_MONOTONE_MAX - 0.001) is Liveliness.MONOTONE
    assert liveliness(PVQ_MONOTONE_MAX) is Liveliness.LIVELY
    assert liveliness(PVQ_LIVELY_MAX - 0.001) is Liveliness.LIVELY
    assert liveliness(PVQ_LIVELY_MAX) is Liveliness.VERY_LIVELY


def test_an_unmeasured_quotient_gets_no_step() -> None:
    assert liveliness(None) is None


def test_a_monotone_contour_reads_as_monotone_and_a_lively_one_as_lively() -> None:
    flat = profile(_steady(120, 400), ())
    lively = profile(_zigzag(120, 6.0, 20, 400), ())

    assert liveliness(flat.pvq) is Liveliness.MONOTONE
    assert liveliness(lively.pvq) is Liveliness.LIVELY


def test_the_scale_is_built_from_the_thresholds_and_carries_its_colours() -> None:
    steps = liveliness_steps()

    assert [s["step"] for s in steps] == [step.value for step in Liveliness]
    assert [s["label"] for s in steps] == ["monoton", "lebendig", "sehr lebendig"]
    assert steps[0]["range"] == "unter 15 %"
    assert steps[1]["range"] == "15 % bis 25 %"
    assert steps[2]["range"] == "über 25 %"
    assert [s["light"] for s in steps] == ["red", "green", "yellow"]


def test_every_step_has_a_colour_and_a_word() -> None:
    assert set(LIGHTS) == set(Liveliness)
    assert set(LABELS) == set(Liveliness)
    assert set(LIGHTS.values()) <= {"green", "yellow", "red"}


def test_the_top_step_is_not_the_red_one() -> None:
    assert LIGHTS[Liveliness.MONOTONE] == "red"
    assert LIGHTS[Liveliness.LIVELY] == "green"
    assert LIGHTS[Liveliness.VERY_LIVELY] == "yellow"


def test_the_step_is_derived_when_the_session_is_read() -> None:
    served = served_detail(RANGE_KEY, {"median_hz": 120.0, "pvq": 0.18})

    assert served == {
        "median_hz": 120.0,
        "pvq": 0.18,
        "liveliness": "lively",
        "liveliness_label": "lebendig",
        "liveliness_light": "green",
    }


def test_a_session_measured_before_the_quotient_gets_no_step() -> None:
    served = served_detail(RANGE_KEY, {"median_hz": 120.0})

    assert served == {"median_hz": 120.0}


def test_serving_leaves_a_detail_that_was_never_measured_alone() -> None:
    assert served_detail(RANGE_KEY, None) is None


def test_utterance_seams_land_on_the_thinned_curve() -> None:
    utterances = (_steady(120, 250), _steady(130, 250), _steady(140, 100))

    marks = utterance_breaks(utterances, 100)

    # 250 frames at 10 ms thinned to 100 ms is 25 points, then 25 more.
    assert marks == [25, 50]


def test_a_call_of_one_utterance_has_no_seams() -> None:
    assert not utterance_breaks((_steady(120, 300),), 100)


def test_two_seams_inside_one_window_are_marked_once() -> None:
    barely_spoke = (_steady(120, 105), _steady(130, 4), _steady(140, 300))

    assert utterance_breaks(barely_spoke, 100) == [10]


def test_the_stated_grid_is_the_one_thinning_produced() -> None:
    assert effective_step_ms(50) == 50
    assert effective_step_ms(25) == 20
    assert len(thin(_steady(120, 100), 25)) == pytest.approx(50, abs=1)


def test_the_band_is_measured_at_both_ends_and_not_assumed_symmetric() -> None:
    # Twice as much room above the median as below it.
    lopsided = _steady(120, 200) + _sweep(120, 170, 100) + _sweep(120, 109, 100)

    shape = profile(lopsided, ())

    assert shape.band_low_st is not None and shape.band_high_st is not None
    assert shape.band_high_st > abs(shape.band_low_st)
    # ... and the two ends still add up to the figure the metric reports.
    assert shape.band_high_st - shape.band_low_st == pytest.approx(shape.range_st, abs=0.05)


def test_movement_is_not_counted_across_the_seam_between_two_utterances() -> None:
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
    assert liveliness(0.18, MIN_VOICED_MS_FOR_READING) is Liveliness.LIVELY
    assert liveliness(0.18, MIN_VOICED_MS_FOR_READING - 1) is None
    assert liveliness(0.18, None) is Liveliness.LIVELY  # not recorded: no reason to withhold


def test_the_level_threshold_is_the_glissando_threshold_over_the_window() -> None:
    window_s = TERMINAL_WINDOW_MS / 1000

    assert TERMINAL_FLAT_ST == pytest.approx(GLISSANDO_ST_S2 / window_s)
    assert TERMINAL_FLAT_ST < 2.0
