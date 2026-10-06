"""Readings of stored measurements, derived on every read (ADR 0091). The API
routes know no metric keys."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from shared.feedback import interruptions, intonation, metrics
from backend.feedback import explanations

Step = dict[str, str | None]


@dataclass(frozen=True)
class Reading:
    """A scale never exists without an explanation (ADR 0078)."""

    # Read at request time, beside the thresholds it explains.
    explanation: str
    # A function, so a recalibration reaches the legend.
    steps: Callable[[], list[Step]] | None = None
    # Adds served fields; returns the detail unchanged when there is nothing to add.
    derive: Callable[[dict], dict] | None = None


def _liveliness(detail: dict) -> dict:
    """Off `pvq`, never off the semitone range (ADR 0077)."""
    step = intonation.liveliness(detail.get("pvq"), detail.get("voiced_ms"))
    if step is None:
        return detail
    return {
        **detail,
        "liveliness": step.value,
        "liveliness_label": intonation.LABELS[step],
        "liveliness_light": intonation.LIGHTS[step],
    }


def _loudness_course(detail: dict) -> dict:
    """One function serves the drawing and the wrap-up's sentence."""
    curve = detail.get("curve_db")
    if not isinstance(curve, list):
        return detail
    course = metrics.loudness_course(curve)
    return detail if course is None else {**detail, "course": course}


def _interruption_light(detail: dict) -> dict:
    """Derived from `hard_offsets_ms`, never stored (ADR 0091)."""
    offsets = detail.get("hard_offsets_ms")
    if not isinstance(offsets, list):
        return detail
    light = interruptions.light_for(len(offsets))
    return {
        **detail,
        # Overwrites any stale stored colour.
        "light": light.value,
        "light_label": interruptions.LABELS[light],
    }


# Callers use the functions below, so a new entry reaches every route.
_READINGS: dict[str, Reading] = {
    # The two with a scale; wording beside the thresholds (ADR 0078).
    intonation.RANGE_KEY: Reading(
        intonation.EXPLANATION, intonation.liveliness_steps, _liveliness,
    ),
    interruptions.COUNT_KEY: Reading(
        interruptions.EXPLANATION, interruptions.light_steps, _interruption_light,
    ),
    # Every active metric must be here (ADR 0098).
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
    metrics.LOUDNESS_KEY: Reading(explanations.LOUDNESS, derive=_loudness_course),
}


def notes() -> dict[str, str]:
    return {key: reading.explanation for key, reading in _READINGS.items()}


def scales() -> dict[str, list[Step]]:
    return {
        key: reading.steps()
        for key, reading in _READINGS.items() if reading.steps
    }


def served_detail(key: str, detail: dict | None) -> dict | None:
    """The export deliberately does not call this: it copies what is held."""
    if detail is None:
        return None
    reading = _READINGS.get(key)
    return reading.derive(detail) if reading and reading.derive else detail


def explained_keys() -> frozenset[str]:
    return frozenset(_READINGS)
