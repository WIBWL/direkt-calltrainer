"""What a stored Measurement means when it is read back.

A measurement is computed once, when the call ends, and kept (`metrics.py`). A
**reading** is the step of a scale that figure lands on, and it is derived on
every read instead -- because the thresholds behind it are working values that
nothing has validated, and a stored step would outlive the scale it came from.

The split has already paid for itself once: F-35's reading moved from the
semitone range onto the pitch variation quotient, and every stored Session
picked up the new scale on its next read, or lost its step where the new input
had never been measured. No migration, and the audio to re-measure from is long
gone (ADR 0048).

Three tables used to sit in `backend/api/sessions.py` -- which metrics carry an
explanation, which carry a scale, and which need fields added to their stored
detail. An HTTP route is the wrong place to keep a list of metrics: give a new
one a scale and a reading and it measures, stores and serves correctly while
arriving with no explanation, no scale and no step, and nothing fails. Here the
three are one entry per metric, beside the thresholds they describe.

The route now knows no metric keys at all.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from backend.feedback import interruptions, intonation, metrics

# One step of a scale as the interface shows it: the machine-readable name, how
# it is said, where it applies, and a colour where the scale has a direction.
Step = dict[str, str | None]


@dataclass(frozen=True)
class Reading:
    """What one metric offers a reader beyond its figure.

    `explanation` is required and the other two are not, on purpose: ADR 0078
    lets a scale exist only beside the population its boundaries came from, so
    a scale with nothing to read next to it is a threshold the user cannot
    argue with. The reverse is fine -- `run_length` is explained at length and
    deliberately carries no step, because a correlation is not a boundary.
    """

    # The text behind the metric's "i", read from the constant at request time
    # rather than stored with the Session or copied into the frontend: it
    # explains the thresholds it sits beside, and the two are edited together
    # (the arrangement ADR 0063 chose for the field limits).
    explanation: str
    # The whole scale, written out. A function rather than a value, so a
    # recalibration reaches the legend without anything here being touched.
    steps: Callable[[], list[Step]] | None = None
    # Fields added to the stored detail at request time. Takes the detail as it
    # was written and returns it, unchanged where this call gives the reading
    # nothing to work from.
    derive: Callable[[dict], dict] | None = None


def _liveliness(detail: dict) -> dict:
    """F-35's step, off the pitch variation quotient in the detail and not off
    the Measurement's own value, which is the semitone range.

    The two are different figures and only one of them has a boundary anybody
    has published (see `intonation.liveliness`). A Session measured before the
    quotient existed carries no `pvq` and gets no step, which is the honest
    answer rather than a gap papered over with the withdrawn scale.
    """
    step = intonation.liveliness(detail.get("pvq"), detail.get("voiced_ms"))
    if step is None:
        return detail
    return {
        **detail,
        "liveliness": step.value,
        "liveliness_label": intonation.LABELS[step],
        # The colour travels with the word, from beside the threshold that
        # decided both. The frontend maps no step to any colour of its own.
        "liveliness_light": intonation.LIGHTS[step],
    }


def _light_label(detail: dict) -> dict:
    """F-51's traffic light in words. The step itself is stored, unlike F-35's
    -- this light predates the derive-on-read arrangement -- so only the German
    is added, which keeps it beside the thresholds it describes."""
    try:
        light = interruptions.TrafficLight(detail.get("light"))
    except ValueError:
        return detail  # measured before the light existed, or a value since retired
    return {**detail, "light_label": interruptions.LABELS[light]}


# One entry per metric that says anything beyond its figure. Private: callers
# ask the three functions below, so adding a metric here reaches every route
# without any of them learning about it.
_READINGS: dict[str, Reading] = {
    intonation.RANGE_KEY: Reading(
        intonation.EXPLANATION, intonation.liveliness_steps, _liveliness,
    ),
    interruptions.COUNT_KEY: Reading(
        interruptions.EXPLANATION, interruptions.light_steps, _light_label,
    ),
    metrics.RUN_LENGTH_KEY: Reading(metrics.RUN_LENGTH_EXPLANATION),
}


def notes() -> dict[str, str]:
    """The long explanation behind each metric's "i", by metric key."""
    return {key: reading.explanation for key, reading in _READINGS.items()}


def scales() -> dict[str, list[Step]]:
    """The scales those readings come from, written out, by metric key.

    A boundary the user cannot see is a judgement they cannot argue with, and
    every boundary in here is a working value (see the two modules).
    """
    return {
        key: reading.steps()
        for key, reading in _READINGS.items() if reading.steps
    }


def served_detail(key: str, detail: dict | None) -> dict | None:
    """The stored facts, plus whatever this metric's reading adds to them.

    A metric with no reading, and a Session whose detail was never written, are
    both served exactly as stored -- which is also what `GET /api/me/export`
    serves in every case, deliberately: an export is a copy of what is held,
    not of what is concluded from it.
    """
    if detail is None:
        return None
    reading = _READINGS.get(key)
    return reading.derive(detail) if reading and reading.derive else detail


def explained_keys() -> frozenset[str]:
    """Every metric key this module speaks for. For the tests that pin those
    keys against the inventory in `metrics.py`."""
    return frozenset(_READINGS)
