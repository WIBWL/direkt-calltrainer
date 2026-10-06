"""Explanations, scales and derived steps per metric (ADR 0078, 0091, 0098)."""
import pytest

from shared.feedback import intonation, metrics
from backend.feedback import readings

# pylint: disable=missing-function-docstring


def test_every_explained_key_is_a_metric_that_exists():
    inventory = {m.key for m in metrics.METRICS}
    assert readings.explained_keys() <= inventory


def test_every_active_metric_is_explained():
    active = {m.key for m in metrics.METRICS if m.active}
    assert active <= readings.explained_keys(), sorted(active - readings.explained_keys())


def test_every_scale_belongs_to_a_metric_that_is_explained():
    assert set(readings.scales()) <= set(readings.notes())


@pytest.mark.parametrize("key", sorted(readings.scales()))
def test_a_scale_is_written_out_in_words_and_not_only_in_colour(key):
    steps = readings.scales()[key]
    assert len(steps) >= 2, "a scale of one step states nothing"
    for step in steps:
        assert step["step"], key
        assert step["label"], f"{key}: a step with no words is colour alone"
        assert step["range"], f"{key}: a step with no span cannot be argued with"


@pytest.mark.parametrize("key", sorted(readings.scales()))
def test_a_scale_carries_a_colour_on_every_step_or_on_none(key):
    coloured = [step["light"] is not None for step in readings.scales()[key]]
    assert all(coloured) or not any(coloured), key


def test_the_melody_step_is_read_off_the_quotient_and_not_off_the_range():
    served = readings.served_detail(intonation.RANGE_KEY, {"pvq": 0.05, "voiced_ms": 60_000})
    assert served["liveliness"] == intonation.Liveliness.MONOTONE.value
    assert served["liveliness_label"] == intonation.LABELS[intonation.Liveliness.MONOTONE]
    assert served["liveliness_light"] == intonation.LIGHTS[intonation.Liveliness.MONOTONE]


def test_a_session_measured_before_the_quotient_gets_no_step():
    stored = {"range_st": 9.0}
    assert readings.served_detail(intonation.RANGE_KEY, stored) == stored


def test_a_metric_with_no_reading_is_served_exactly_as_stored():
    stored = {"user_ms": 1000, "persona_ms": 2000}
    assert readings.served_detail("talk_share", stored) is stored


def test_a_measurement_with_no_detail_stays_without_one():
    assert readings.served_detail(intonation.RANGE_KEY, None) is None


# A step is derived on read, never stored (ADR 0091).

_READING_KEYS = frozenset({
    "light", "light_label",
    "liveliness", "liveliness_label", "liveliness_light",
})


def test_no_measurement_stores_a_step_or_a_colour():
    from shared.tests.test_metrics import _call_with_a_barge_in  # pylint: disable=import-outside-toplevel
    from shared.feedback.calls import conversation  # pylint: disable=import-outside-toplevel

    for measurement in metrics.measure(conversation(_call_with_a_barge_in(), "de")):
        stored = set(measurement.detail or {})
        assert not stored & _READING_KEYS, f"{measurement.key} stores a reading: {stored & _READING_KEYS}"


def test_a_recalibrated_threshold_reaches_a_call_already_measured(monkeypatch):
    from shared.feedback import interruptions  # pylint: disable=import-outside-toplevel

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
    from shared.feedback import interruptions  # pylint: disable=import-outside-toplevel

    stale = {"hard_offsets_ms": [], "light": "red"}

    assert readings.served_detail(interruptions.COUNT_KEY, stale)["light"] == "green"


def _steady(points: int, level: float = 65.0) -> list[float | None]:
    """Steady without being constant, like real Praat output."""
    return [level + (index % 5) - 2 for index in range(points)]


def _with_stretch(shift: float, length: int, at: int) -> list[float | None]:
    curve = _steady(600)
    for index in range(at, at + length):
        curve[index] = curve[index] + shift
    return curve


def test_the_loudness_course_is_served_beside_the_stored_curve():
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
    stored = {"span_db": 12.0}

    assert readings.served_detail(metrics.LOUDNESS_KEY, stored) == stored


@pytest.mark.parametrize(
    ("curve", "described"),
    [(_steady(600), False), (_with_stretch(shift=10.0, length=60, at=450), True)],
)
def test_the_sentence_and_the_drawing_read_the_same_call(curve, described: bool):
    served = readings.served_detail(metrics.LOUDNESS_KEY, {"curve_db": curve})
    sentence = metrics.describe_loudness_course(curve)

    assert bool(served["course"]["stretches"]) is described
    assert ("stretch" in sentence) is described
