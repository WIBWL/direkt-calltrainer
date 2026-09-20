"""What a stored Measurement says beyond its figure, and the shape ADR 0078
requires it to say it in.

`backend/feedback/readings.py` holds one entry per metric that carries an
explanation, a scale or a step derived on read. Those three used to be three
tables inside `backend/api/sessions.py`, where a metric key could be misspelt
or outlive its metric and the route would go on serving a dictionary nobody
could match to anything.

The conditions pinned here are ADR 0078's, and they are pinned structurally
rather than left to care: a scale that loses its words, or gains a colour on
one step and not the next, is a traffic light asserting a direction it never
wrote down.

Covers:
  F-35, F-51  the two readings that carry a step
  F-53        every active metric carries an explanation, which is what makes
              its tile openable at all
  F-53        the metric explained at length that deliberately carries none
  ADR 0051    a figure is measured once and stored; a step is not a figure
  ADR 0063    the text lives beside the threshold, not copied into the client
  ADR 0078    what a light on a metric may claim, and under which conditions
"""
import pytest

from backend.feedback import intonation, metrics, readings

# pylint: disable=missing-function-docstring


def test_every_explained_key_is_a_metric_that_exists():
    """A key here that no metric answers to serves text nothing can show."""
    inventory = {m.key for m in metrics.METRICS}
    assert readings.explained_keys() <= inventory


def test_every_active_metric_is_explained():
    """The condition behind "every tile opens".

    A Kennzahl tile on the wrap-up screen becomes a link when this module
    speaks for its metric -- that is what `MetricSection` reads `metric_notes`
    for. Three of sixteen used to, so thirteen tiles stated a figure and
    offered no way to see what it was read off.

    Pinned as a rule and not as a count: a metric added to the inventory
    without a word about it is exactly the drift `readings.py` was split out to
    make visible, and it would arrive silently again.
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
# Everything above is the reading side. This is the invariant the module exists
# for, and it had no test: F-51's step was being stored in the measurement's
# detail and served back from there, which is exactly what ADR 0091 forbids and
# exactly what ADR 0077 had already had to undo once for F-35.

_READING_KEYS = frozenset({
    "light", "light_label",
    "liveliness", "liveliness_label", "liveliness_light",
})


def test_no_measurement_stores_a_step_or_a_colour():
    """The detail a call writes holds facts and no judgement about them.

    Named keys rather than a diff against `served_detail`: a key that is both
    stored and derived would make the diff empty, which is the very state this
    has to catch.
    """
    from tests.test_metrics import _call_with_a_barge_in  # pylint: disable=import-outside-toplevel
    from backend.feedback.calls import conversation  # pylint: disable=import-outside-toplevel

    for measurement in metrics.measure(conversation(_call_with_a_barge_in(), "de")):
        stored = set(measurement.detail or {})
        assert not stored & _READING_KEYS, f"{measurement.key} stores a reading: {stored & _READING_KEYS}"


def test_a_recalibrated_threshold_reaches_a_call_already_measured(monkeypatch):
    """The property the split is for, stated end to end.

    The two numbers behind F-51's light are invented working values, and the
    module says so: they are meant to be recalibrated once the pilot has data.
    A stored step survives that recalibration, and then the interface shows a
    figure coloured by the old scale beside a legend built from the new one --
    a red 3 next to a legend putting 3 in the yellow band, with the current
    step marked in a band the number is not in.
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
