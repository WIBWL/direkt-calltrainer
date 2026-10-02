"""What a stored Measurement means when it is read back (ADR 0091).
A measurement is stored once; a **reading** (the step it lands on) is derived on
every read, so a recalibrated scale reaches old Sessions without a migration.
One entry per metric here; the API routes know no metric keys.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from backend.feedback import explanations, interruptions, intonation, metrics

# One step of a scale as the interface shows it: the machine-readable name, how
# it is said, where it applies, and a colour where the scale has a direction.
Step = dict[str, str | None]


@dataclass(frozen=True)
class Reading:
    """What one metric offers a reader beyond its figure. A scale never exists
    without an explanation (ADR 0078's fourth condition); an explanation without
    a scale is fine. `derive` may add served fields, as `loudness` does.
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
    """F-35's step, off the `pvq` in the detail -- never off the Measurement's own
    value, the semitone range, which has no published boundary. No `pvq`, no step
    (see `intonation.liveliness`).
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


def _loudness_course(detail: dict) -> dict:
    """F-37's course (smoothed line, own band, stretches outside it), served so
    the drawing and the wrap-up's sentence (`metrics.describe_loudness_course`)
    come from one function. A curve too short to read is served as stored.
    """
    curve = detail.get("curve_db")
    if not isinstance(curve, list):
        return detail
    course = metrics.loudness_course(curve)
    return detail if course is None else {**detail, "course": course}


def _interruption_light(detail: dict) -> dict:
    """F-51's traffic light, colour and word, derived on read from the length of
    `hard_offsets_ms` -- never stored, or it would outlive a recalibration
    (ADR 0091). A detail without that list gets no light.
    """
    offsets = detail.get("hard_offsets_ms")
    if not isinstance(offsets, list):
        return detail
    light = interruptions.light_for(len(offsets))
    return {
        **detail,
        # Written explicitly, so a colour stored by an older version of this
        # code is replaced on read rather than left to win.
        "light": light.value,
        "light_label": interruptions.LABELS[light],
    }


# One entry per metric that says anything beyond its figure. Private: callers
# ask the three functions below, so adding a metric here reaches every route
# without any of them learning about it.
_READINGS: dict[str, Reading] = {
    # The two with a scale. Their wording lives beside the thresholds it
    # describes, which is ADR 0078's fifth condition.
    intonation.RANGE_KEY: Reading(
        intonation.EXPLANATION, intonation.liveliness_steps, _liveliness,
    ),
    interruptions.COUNT_KEY: Reading(
        interruptions.EXPLANATION, interruptions.light_steps, _interruption_light,
    ),
    # The rest: explained, deliberately without a step. Every active metric must
    # be here, or its tile states a figure with no way to check it (ADR 0098).
    metrics.RUN_LENGTH_KEY: Reading(explanations.RUN_LENGTH),
    "talk_share": Reading(explanations.TALK_SHARE),
    "questions": Reading(explanations.QUESTIONS),
    "pace": Reading(explanations.PACE),
    "word_count": Reading(explanations.WORD_COUNT),
    "fillers": Reading(explanations.FILLERS),
    "opening": Reading(explanations.OPENING),
    metrics.CLOSING_KEY: Reading(explanations.CLOSING),
    "repetitions": Reading(explanations.REPETITIONS),
    "hesitations": Reading(explanations.HESITATIONS),
    "reaction_time": Reading(explanations.REACTION_TIME),
    "pauses": Reading(explanations.PAUSES),
    "phonation_share": Reading(explanations.PHONATION_SHARE),
    # Explained like the rest, and the only one of them that also derives:
    # the course the screen draws is read here (ADR 0091), never stored.
    metrics.LOUDNESS_KEY: Reading(explanations.LOUDNESS, derive=_loudness_course),
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
    """The stored facts, plus whatever this metric's reading adds to them. The
    export deliberately does not call this: it copies what is held, not what is
    concluded from it.
    """
    if detail is None:
        return None
    reading = _READINGS.get(key)
    return reading.derive(detail) if reading and reading.derive else detail


def explained_keys() -> frozenset[str]:
    """Every metric key this module speaks for. For the tests that pin those
    keys against the inventory in `metrics.py`."""
    return frozenset(_READINGS)
