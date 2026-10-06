"""The shape of a speaker's pitch across a call (F-35), in semitones from their
median. Only the liveliness (PVQ) carries a reading (ADR 0077)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

STEP_MS = 10

# The final syllable or two, where a German phrase puts its nuclear movement.
TERMINAL_WINDOW_MS = 400

# Glissando threshold G = 0.32 / T² ST/s for continuous speech (Mertens 2004),
# not the 0.16 of isolated vowels.
GLISSANDO_ST_S2 = 0.32

# Derived, not chosen: 0.8 ST over 400 ms. Unverified on real calls.
TERMINAL_FLAT_ST = round(GLISSANDO_ST_S2 / (TERMINAL_WINDOW_MS / 1000), 2)
MIN_TERMINAL_FRAMES = 8

# A bigger jump between frames is the tracker, not a voice. A heuristic bound.
MAX_STEP_ST = 6.0

# Measured: 2 % tracker noise inflated the raw figure 29 %; three frames cost
# 4.5 % and damp real movement 5 %.
MOVEMENT_SMOOTH_FRAMES = 3

MIN_VOICED_FRAMES = 20

# Hincks (2005): SD over mean of F0 per window, in Hz. Kept to her definition,
# or her boundaries do not apply.
PVQ_WINDOW_MS = 10_000

# Our floor (her pause rule does not fit a contour without inter-utterance pauses).
MIN_VOICED_SHARE_IN_WINDOW = 0.3

RANGE_KEY = "intonation"

# A judgement, allowed only on the single-call view (ADR 0077/0078). Validated
# (r = 0.83) on 18 Swedish students in L2 English, not this population.
PVQ_MONOTONE_MAX = 0.15
PVQ_LIVELY_MAX = 0.25

# A floor for a step, not a sufficiency: Hincks's reliability rests on nine windows.
MIN_VOICED_MS_FOR_READING = 10_000


@dataclass(frozen=True)
class Endings:
    """Counts, not a score: falling closes, rising leaves open, neither is better."""

    falling: int = 0
    rising: int = 0
    level: int = 0

    @property
    def total(self) -> int:
        return self.falling + self.rising + self.level


@dataclass(frozen=True)
class Profile:  # pylint: disable=too-many-instance-attributes  # a record of measurements
    range_st: float | None = None
    # Measured, not assumed symmetric: a voice reaches further one way.
    band_low_st: float | None = None
    band_high_st: float | None = None
    # Semitones per second of voiced speech.
    movement_st_per_s: float | None = None
    # The reading rests on this alone.
    pvq: float | None = None
    pvq_windows: int = 0
    voiced_ms: int = 0
    endings: Endings = Endings()
    # First and last third, so a change within the speaker can be stated.
    range_first_st: float | None = None
    range_last_st: float | None = None
    # Only for reading semitones back into Hz; never compared.
    median_hz: float | None = None


def semitones(hz: float, reference_hz: float) -> float:
    return 12 * math.log2(hz / reference_hz)


def profile(contour: tuple[float | None, ...], per_utterance: tuple[tuple[float | None, ...], ...]) -> Profile:
    voiced = [hz for hz in contour if hz]
    if len(voiced) < MIN_VOICED_FRAMES:
        return Profile()

    median = _median(sorted(voiced))
    thirds = _thirds(contour)
    band = _band(voiced)
    quotient, windows = _pvq(contour)
    return Profile(
        range_st=_range_st(voiced),
        band_low_st=None if band is None else round(semitones(band[0], median), 2),
        band_high_st=None if band is None else round(semitones(band[1], median), 2),
        movement_st_per_s=_movement(per_utterance or (contour,)),
        pvq=quotient,
        pvq_windows=windows,
        voiced_ms=len(voiced) * STEP_MS,
        endings=_endings(per_utterance),
        range_first_st=_range_st([hz for hz in thirds[0] if hz]),
        range_last_st=_range_st([hz for hz in thirds[2] if hz]),
        median_hz=round(median, 1),
    )


def _band(voiced: list[float]) -> tuple[float, float] | None:
    """5th-95th percentile in Hz, shared by the span and the drawn band."""
    if len(voiced) < MIN_VOICED_FRAMES:
        return None
    ordered = sorted(voiced)
    margin = len(ordered) // 20
    low, high = ordered[margin], ordered[-1 - margin]
    if low <= 0 or high < low:
        return None
    return low, high


def _range_st(voiced: list[float]) -> float | None:
    band = _band(voiced)
    return None if band is None else round(semitones(band[1], band[0]), 2)


def _pvq(contour: tuple[float | None, ...]) -> tuple[float | None, int]:
    """Mean PVQ and its window count. A short remainder is dropped unless no full
    window was seen (asked of windows seen, not quotients kept)."""
    per_window = PVQ_WINDOW_MS // STEP_MS
    quotients: list[float] = []
    full_windows_seen = False
    for start in range(0, len(contour), per_window):
        window = contour[start:start + per_window]
        if len(window) < per_window and full_windows_seen:
            break
        full_windows_seen = full_windows_seen or len(window) == per_window
        voiced = [hz for hz in window if hz]
        floor = max(MIN_VOICED_FRAMES, int(len(window) * MIN_VOICED_SHARE_IN_WINDOW))
        if len(voiced) < floor:
            continue
        mean = sum(voiced) / len(voiced)
        variance = sum((hz - mean) ** 2 for hz in voiced) / (len(voiced) - 1)
        quotients.append(math.sqrt(variance) / mean)
    if not quotients:
        return None, 0
    return round(sum(quotients) / len(quotients), 4), len(quotients)


def _movement(per_utterance: tuple[tuple[float | None, ...], ...]) -> float | None:
    """Per utterance then pooled: across utterances the seam would count as
    movement. Steps over MAX_STEP_ST are octave errors."""
    steps: list[float] = []
    for utterance in per_utterance:
        smoothed = _smooth(utterance)
        for before, after in zip(smoothed, smoothed[1:]):
            if not before or not after:
                continue  # a voicing gap is not a movement
            step = abs(semitones(after, before))
            if step <= MAX_STEP_ST:
                steps.append(step)
    if len(steps) < MIN_VOICED_FRAMES:
        return None
    return round(sum(steps) / len(steps) * (1000 / STEP_MS), 2)


def _smooth(contour: tuple[float | None, ...]) -> tuple[float | None, ...]:
    """A median (a mean would spread a stray frame); unvoiced stays unvoiced."""
    half = MOVEMENT_SMOOTH_FRAMES // 2
    out: list[float | None] = []
    for index, hz in enumerate(contour):
        if not hz:
            out.append(None)
            continue
        window = [v for v in contour[max(0, index - half):index + half + 1] if v]
        out.append(_median(sorted(window)))
    return tuple(out)


def _endings(per_utterance: tuple[tuple[float | None, ...], ...]) -> Endings:
    """Over the last TERMINAL_WINDOW_MS of voiced frames."""
    falling = rising = level = 0
    for utterance in per_utterance:
        read = _terminal_slope(utterance)
        if read is None:
            continue
        movement, frames = read
        flat = _flat_threshold_st(frames)
        if movement <= -flat:
            falling += 1
        elif movement >= flat:
            rising += 1
        else:
            level += 1
    return Endings(falling=falling, rising=rising, level=level)


def _flat_threshold_st(frames: int) -> float:
    """The level threshold for the window actually read: a short utterance needs
    a higher floor, or inaudible movements count. `frames - 1` intervals."""
    return GLISSANDO_ST_S2 / (max(frames - 1, 1) * STEP_MS / 1000)


def _terminal_slope(utterance: tuple[float | None, ...]) -> tuple[float, int] | None:
    """Final movement in semitones (negative = falling) and the frame count. A
    least-squares fit: endpoints are the noisiest frames, and half-means halve
    every movement."""
    voiced = [hz for hz in utterance if hz]
    window = TERMINAL_WINDOW_MS // STEP_MS
    if len(voiced) < MIN_TERMINAL_FRAMES:
        return None
    tail = voiced[-window:]
    if len(tail) < MIN_TERMINAL_FRAMES:
        return None

    reference = tail[0]
    values = [semitones(hz, reference) for hz in tail]
    count = len(values)
    mean_x = (count - 1) / 2
    mean_y = sum(values) / count
    variance = sum((i - mean_x) ** 2 for i in range(count))
    if variance == 0:
        return None
    slope = sum((i - mean_x) * (y - mean_y) for i, y in enumerate(values)) / variance
    return round(slope * (count - 1), 2), count


def _thirds(contour: tuple[float | None, ...]) -> tuple[tuple[float | None, ...], ...]:
    """Thirds of voiced speech, not of the clock, so silence cannot swallow one."""
    voiced_positions = [i for i, hz in enumerate(contour) if hz]
    if len(voiced_positions) < 3:
        return ((), (), ())
    cut = len(voiced_positions) // 3
    first_end = voiced_positions[cut]
    last_start = voiced_positions[2 * cut]
    return (contour[:first_end], contour[first_end:last_start], contour[last_start:])


def _median(ordered: list[float]) -> float:
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def effective_step_ms(step_ms: int) -> int:
    """The grid `thin` really produces (25 ms -> 20 ms). State this, not the
    request, or the drawing's axis lies."""
    return _per_point(step_ms) * STEP_MS


def _per_point(step_ms: int) -> int:
    return max(1, step_ms // STEP_MS)


def thin(contour: tuple[float | None, ...], step_ms: int) -> list[float | None]:
    """A coarser grid for storage and drawing only; median per window."""
    per_point = _per_point(step_ms)
    out: list[float | None] = []
    for start in range(0, len(contour), per_point):
        window = [hz for hz in contour[start:start + per_point] if hz]
        out.append(round(_median(sorted(window)), 1) if window else None)
    return out


def utterance_breaks(
    per_utterance: tuple[tuple[float | None, ...], ...], step_ms: int
) -> list[int]:
    """Seams between utterances as indices into the thinned curve, so a seam is
    not read as movement."""
    per_point = _per_point(step_ms)
    total = sum(len(utterance) for utterance in per_utterance)
    points = -(-total // per_point)

    marks: list[int] = []
    frames = 0
    for utterance in per_utterance[:-1]:
        frames += len(utterance)
        index = frames // per_point
        if 0 < index < points and index not in marks:
            marks.append(index)
    return marks


class Liveliness(str, Enum):
    """Hincks's three steps. Never add a step between them: that would be an
    invented boundary."""

    MONOTONE = "monotone"
    LIVELY = "lively"
    # The liveliest speakers in Hincks's corpus, not "too much".
    VERY_LIVELY = "very_lively"


LABELS: dict[Liveliness, str] = {
    Liveliness.MONOTONE: "monoton",
    Liveliness.LIVELY: "lebendig",
    Liveliness.VERY_LIVELY: "sehr lebendig",
}

# ADR 0078: the colours point, they do not grade.
#   monotone     red     look here: on the phone a flat delivery costs emphasis
#   lively       green   nothing needs attention
#   very_lively  yellow  NOT "too expressive": the figure is least trustworthy
#                        here (octave errors, nervousness); look at the contour
LIGHTS: dict[Liveliness, str] = {
    Liveliness.MONOTONE: "red",
    Liveliness.LIVELY: "green",
    Liveliness.VERY_LIVELY: "yellow",
}

# One table for the decision and the legend.
_LADDER: tuple[tuple[float, Liveliness], ...] = (
    (PVQ_MONOTONE_MAX, Liveliness.MONOTONE),
    (PVQ_LIVELY_MAX, Liveliness.LIVELY),
)

EXPLANATION = (
    "Die Zahl der Kennzahl ist der Umfang: der Abstand zwischen Ihrem tiefsten "
    "und Ihrem höchsten üblichen Ton, in Halbtönen. Halbtöne statt Hertz, damit "
    "eine tiefe und eine hohe Stimme bei gleicher Lebendigkeit dieselbe Zahl "
    "bekommen. Zum Umfang selbst sagen wir nichts, denn es gibt keinen belegten "
    "Wert dafür, ab wann eine Spanne eng oder weit ist. "
    "Die farbige Einstufung stammt deshalb aus einer anderen Größe, der "
    "Lebendigkeit. Sie misst, wie stark Ihre Tonhöhe um Ihre eigene mittlere "
    "Stimmlage schwankt, jeweils über zehn Sekunden Sprechzeit. Für diese Größe "
    "gibt es Grenzwerte, die gegen das Urteil echter Zuhörer geprüft wurden. "
    "Geprüft wurden sie allerdings an 18 schwedischen Studierenden, die auf "
    "Englisch im Seminarraum präsentiert haben, nicht an deutschen "
    "Telefongesprächen. Nehmen Sie die Farbe deshalb als Hinweis und nicht als "
    "Urteil. Wie viel Melodie passend ist, hängt außerdem vom Anlass ab: eine "
    "Reklamation klingt zu Recht anders als ein Verkaufsgespräch."
)


def liveliness(pvq: float | None, voiced_ms: int | None = None) -> Liveliness | None:
    """No step below MIN_VOICED_MS_FOR_READING or without a PVQ. Never derive
    one from the range: that would reinstate the withdrawn scale (ADR 0077)."""
    if pvq is None:
        return None
    if voiced_ms is not None and voiced_ms < MIN_VOICED_MS_FOR_READING:
        return None
    for bound, step in _LADDER:
        if pvq < bound:
            return step
    return Liveliness.VERY_LIVELY


def liveliness_steps() -> list[dict[str, str | None]]:
    """The whole scale with its lights, built from the constants (ADR 0078)."""
    spans: list[tuple[Liveliness, str]] = []
    floor: float | None = None
    for bound, step in _LADDER:
        spans.append((step, f"unter {_percent(bound)}" if floor is None
                      else f"{_percent(floor)} bis {_percent(bound)}"))
        floor = bound
    spans.append((Liveliness.VERY_LIVELY, f"über {_percent(floor)}"))
    return [
        {"step": step.value, "label": LABELS[step], "range": span, "light": LIGHTS[step]}
        for step, span in spans
    ]


def _percent(value: float) -> str:
    return f"{value * 100:g} %"
