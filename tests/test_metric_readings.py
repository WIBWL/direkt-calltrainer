"""What a stored Measurement says beyond its figure, in ADR 0078's required shape.

`readings.py` holds explanation, scale and derived step per metric. Covers F-35,
F-51 (steps), F-53 (every active metric explained), F-37 (loudness course), ADR 0051,
ADR 0063 (text beside the threshold) and ADR 0078's conditions, pinned structurally."""
import pytest

from backend.feedback import intonation, metrics, readings

# pylint: disable=missing-function-docstring


def test_every_explained_key_is_a_metric_that_exists():
    """A key here that no metric answers to serves text nothing can show."""
    inventory = {m.key for m in metrics.METRICS}
    assert readings.explained_keys() <= inventory


def test_every_active_metric_is_explained():
    """Every active metric is explained: the condition behind "every tile opens".

    `MetricSection` links a tile only when `metric_notes` covers its metric. Pinned as
    a rule, not a count, so a new metric without a word about it fails here.
    """
    active = {m.key for m in metrics.METRICS if m.active}
    assert active <= readings.explained_keys(), sorted(active - readings.explained_keys())


def test_every_scale_belongs_to_a_metric_that_is_explained():
    """ADR 0078's fourth condition: a boundary is shown beside the population
    it came from. A scale with no explanation next to it is a threshold the
    user cannot argue with."""
    assert set(readings.scales()) <= set(readings.notes())


@pytest.mark.parametrize("key", sorted(readings.scales()))
def test_a_scale_is_written_out_in_words_and_not_only_in_colour(key):
    """ADR 0078's second and third conditions, together: the whole scale is
    visible, every step is said in words, and the colour is never the only
    thing carrying the step."""
    steps = readings.scales()[key]
    assert len(steps) >= 2, "a scale of one step states nothing"
    for step in steps:
        assert step["step"], key
        assert step["label"], f"{key}: a step with no words is colour alone"
        assert step["range"], f"{key}: a step with no span cannot be argued with"


@pytest.mark.parametrize("key", sorted(readings.scales()))
def test_a_scale_carries_a_colour_on_every_step_or_on_none(key):
    """Half a traffic light is the worst of both: the steps without a colour
    read as the absence of a finding rather than as a scale with no direction.
    """
    coloured = [step["light"] is not None for step in readings.scales()[key]]
    assert all(coloured) or not any(coloured), key


def test_the_melody_step_is_read_off_the_quotient_and_not_off_the_range():
    """The Measurement's own value is the semitone range, which has no
    published boundary; the step comes from `pvq` in the detail (ADR 0077)."""
    served = readings.served_detail(intonation.RANGE_KEY, {"pvq": 0.05, "voiced_ms": 60_000})
    assert served["liveliness"] == intonation.Liveliness.MONOTONE.value
    assert served["liveliness_label"] == intonation.LABELS[intonation.Liveliness.MONOTONE]
    assert served["liveliness_light"] == intonation.LIGHTS[intonation.Liveliness.MONOTONE]


def test_a_session_measured_before_the_quotient_gets_no_step():
    """The honest answer for a call whose audio is gone (ADR 0048): four
    figures and no reading, rather than the withdrawn scale under a new name.
    """
    stored = {"range_st": 9.0}
    assert readings.served_detail(intonation.RANGE_KEY, stored) == stored


def test_a_metric_with_no_reading_is_served_exactly_as_stored():
    stored = {"user_ms": 1000, "persona_ms": 2000}
    assert readings.served_detail("talk_share", stored) is stored


def test_a_measurement_with_no_detail_stays_without_one():
    assert readings.served_detail(intonation.RANGE_KEY, None) is None


# --- A reading is not written down (ADR 0091) --------------------------------
#
# The invariant the module exists for: a step is derived on read, never stored
# in the measurement's detail (ADR 0077 had to undo exactly that for F-35).

_READING_KEYS = frozenset({
    "light", "light_label",
    "liveliness", "liveliness_label", "liveliness_light",
})


def test_no_measurement_stores_a_step_or_a_colour():
    """The detail a call writes holds facts and no judgement about them.

    Named keys, not a diff against `served_detail`: a key both stored and derived
    would make the diff empty.
    """
    from tests.test_metrics import _call_with_a_barge_in  # pylint: disable=import-outside-toplevel
    from backend.feedback.calls import conversation  # pylint: disable=import-outside-toplevel

    for measurement in metrics.measure(conversation(_call_with_a_barge_in(), "de")):
        stored = set(measurement.detail or {})
        assert not stored & _READING_KEYS, f"{measurement.key} stores a reading: {stored & _READING_KEYS}"


def test_a_recalibrated_threshold_reaches_a_call_already_measured(monkeypatch):
    """A recalibrated threshold reaches a call already measured.

    F-51's thresholds are invented working values meant to be recalibrated; a stored
    step would show an old-scale colour beside a legend built from the new scale.
    """
    from backend.feedback import interruptions  # pylint: disable=import-outside-toplevel

    stored = {"persona_turns": 8, "call_ms": 70_000, "soft_count": 1,
              "backchannel_count": 0, "hard_offsets_ms": [1_000, 2_000, 3_000]}

    assert readings.served_detail(interruptions.COUNT_KEY, stored)["light"] == "red"

    monkeypatch.setattr(interruptions, "GREEN_MAX_COUNT", 2)
    monkeypatch.setattr(interruptions, "YELLOW_MAX_COUNT", 5)

    served = readings.served_detail(interruptions.COUNT_KEY, stored)
    assert served["light"] == "yellow", "the same three interruptions, read against the new scale"
    assert served["light_label"] == interruptions.LABELS[interruptions.TrafficLight.YELLOW]
    # And the legend served beside it says the same thing about the same count.
    band = next(s for s in readings.scales()[interruptions.COUNT_KEY] if s["light"] == "yellow")
    assert band["range"] == "3 bis 5"


def test_a_colour_stored_by_an_older_version_does_not_win():
    """Rows written before the step was taken out still carry it. The reading
    replaces it rather than leaving it in place, or those Sessions would keep
    the frozen colour this change exists to remove."""
    from backend.feedback import interruptions  # pylint: disable=import-outside-toplevel

    stale = {"hard_offsets_ms": [], "light": "red"}

    assert readings.served_detail(interruptions.COUNT_KEY, stale)["light"] == "green"


# --- F-37: the course the screen draws and the prompt describes ------------

def _steady(points: int, level: float = 65.0) -> list[float | None]:
    """Steady without being constant, like real Praat output."""
    return [level + (index % 5) - 2 for index in range(points)]


def _with_stretch(shift: float, length: int, at: int) -> list[float | None]:
    curve = _steady(600)
    for index in range(at, at + length):
        curve[index] = curve[index] + shift
    return curve


def test_the_loudness_course_is_served_beside_the_stored_curve():
    """The band, the smoothed line and the stretches are read on every request
    and never stored (ADR 0091) -- the browser computed all three a second time
    until this was served."""
    stored = {"curve_db": _with_stretch(shift=10.0, length=60, at=450)}

    served = readings.served_detail(metrics.LOUDNESS_KEY, stored)

    assert served["curve_db"] is stored["curve_db"], "the stored curve is unchanged"
    course = served["course"]
    assert len(course["smoothed"]) == len(stored["curve_db"])
    assert course["low"] < course["median"] < course["high"]
    assert [stretch["direction"] for stretch in course["stretches"]] == ["louder"]
    assert 450 <= course["stretches"][0]["peak_index"] < 510


def test_a_curve_too_short_to_read_is_served_exactly_as_stored():
    stored = {"curve_db": [65.0, 66.0, None]}

    assert readings.served_detail(metrics.LOUDNESS_KEY, stored) == stored


def test_a_measurement_without_a_curve_is_served_as_stored():
    """Nothing to read it off, and nothing pretended."""
    stored = {"span_db": 12.0}

    assert readings.served_detail(metrics.LOUDNESS_KEY, stored) == stored


@pytest.mark.parametrize(
    ("curve", "described"),
    [(_steady(600), False), (_with_stretch(shift=10.0, length=60, at=450), True)],
)
def test_the_sentence_and_the_drawing_read_the_same_call(curve, described: bool):
    """The wrap-up's sentence about the course and the course on screen come
    out of one function now. They were two implementations in two languages,
    and a drawing that marked no stretch under a sentence naming one would have
    been nobody's fault in particular."""
    served = readings.served_detail(metrics.LOUDNESS_KEY, {"curve_db": curve})
    sentence = metrics.describe_loudness_course(curve)

    assert bool(served["course"]["stretches"]) is described
    assert ("stretch" in sentence) is described
