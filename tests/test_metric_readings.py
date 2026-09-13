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
