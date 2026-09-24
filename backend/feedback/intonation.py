"""The shape of a speaker's pitch across a call (F-35), as pure functions.
Five figures -- Umfang, Bewegung, Lebendigkeit (Hincks 2005's PVQ), Satzenden,
Verlauf -- in semitones from the speaker's median (Nolan 2003). Only the
Lebendigkeit carries a reading; rationale and caveats in ADR 0077.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

# The analysis grid the contour arrives on (backend/feedback/acoustics.py).
STEP_MS = 10

# How much of an utterance's end the terminal contour is read from: the final
# syllable or two, where a German phrase places its nuclear movement.
TERMINAL_WINDOW_MS = 400

# The glissando threshold G = GLISSANDO_ST_S2 / T**2 ST/s, below which a movement
# of T seconds is heard as a level tone. 0.32 for continuous speech (Mertens
# 2004), not the 0.16 measured on isolated vowels ('t Hart 1976) -- see ADR 0077.
GLISSANDO_ST_S2 = 0.32

# Below this total movement an ending counts as level. Derived, not chosen: the
# glissando threshold across the window is GLISSANDO_ST_S2 / T semitones, 0.8
# over 400 ms (ADR 0077). Unverified on real calls, since the 10 ms contour is
# not stored (ADR 0048).
TERMINAL_FLAT_ST = round(GLISSANDO_ST_S2 / (TERMINAL_WINDOW_MS / 1000), 2)
# A terminal contour needs this many voiced frames in its window to be read at
# all; below it the "slope" would be two points and a guess.
MIN_TERMINAL_FRAMES = 8

# A jump larger than this between neighbouring frames is the tracker changing
# its mind, not a voice; excluded from the movement figure. A heuristic
# plausibility bound on the tracker, not a perceptual threshold.
MAX_STEP_ST = 6.0

# The movement figure is read off a contour median-smoothed over this many
# frames (30 ms). Measured: 2% tracker noise inflated the raw figure by 29%;
# three frames cost 4.5% of it and damp real movement 5%, five frames 13%.
MOVEMENT_SMOOTH_FRAMES = 3

# Below this many voiced frames a factor is not reported at all. Everything here
# is a shape, and a shape needs enough points to have one.
MIN_VOICED_FRAMES = 20

# --- The pitch variation quotient -------------------------------------------
# Hincks (2005): SD over mean of F0, per window, in Hertz (dimensionless, so it
# normalises across voices). Kept exactly to her definition, or her boundaries
# below would not apply.
PVQ_WINDOW_MS = 10_000

# How much of a window has to carry voicing to be usable. Our floor, not
# Hincks's pause rule, which does not apply to a contour with the pauses between
# utterances already removed; 30% only rules out nearly unvoiced windows.
MIN_VOICED_SHARE_IN_WINDOW = 0.3

# The metric this module feeds, named here so the API, the tests and the
# interface agree on the string rather than each spelling it out.
RANGE_KEY = "intonation"

# --- The three-step reading -------------------------------------------------
# Where the PVQ reads as monotone or lively. THIS IS A JUDGEMENT, an exception
# to ADR 0004/0051 confined to the single-call view (ADR 0077/0078). Hincks
# (2005)'s boundaries, validated (r = 0.83) on 18 Swedish students presenting in
# L2 English -- not this population, hence "Einschätzung" in the interface.
PVQ_MONOTONE_MAX = 0.15
PVQ_LIVELY_MAX = 0.25

# How much voiced speech a step needs under it (the figure itself is reported
# from MIN_VOICED_FRAMES). About two to three of Hincks's windows against the
# nine her reliability rests on: a floor, not a sufficiency.
MIN_VOICED_MS_FOR_READING = 10_000


@dataclass(frozen=True)
class Endings:
    """The terminal contours of a call, counted. Falling closes, rising leaves
    open; neither is good or bad, so this is a count, not a score.
    """

    falling: int = 0
    rising: int = 0
    level: int = 0

    @property
    def total(self) -> int:
        """How many utterances were long enough to read an ending from."""
        return self.falling + self.rising + self.level


@dataclass(frozen=True)
class Profile:  # pylint: disable=too-many-instance-attributes  # a record of measurements
    """The five figures, or as many as the contour supported, each carried with
    the material it rests on so it is not read as firmer than it is.
    """

    # 5th to 95th percentile, in semitones. None below MIN_VOICED_FRAMES.
    range_st: float | None = None
    # The two ends of that span, each in semitones from the speaker's median.
    # Reported separately because they are *not* symmetric around it -- a voice
    # reaches further up than down, or the other way about -- and the drawn band
    # would otherwise be a guess dressed as a measurement.
    band_low_st: float | None = None
    band_high_st: float | None = None
    # Mean absolute change between neighbouring voiced frames, in semitones per
    # second of voiced speech.
    movement_st_per_s: float | None = None
    # The pitch variation quotient, averaged over the windows it could be
    # measured in, and how many those were. Dimensionless: a standard deviation
    # of F0 over its mean, both in Hertz. The reading below rests on this and on
    # nothing else.
    pvq: float | None = None
    pvq_windows: int = 0
    # How much voiced speech the figures rest on. The reading below has a floor
    # under it: five steps read off two seconds of humming would be a verdict on
    # nothing.
    voiced_ms: int = 0
    endings: Endings = Endings()
    # The range of the first third of the call and of the last, so a widening
    # or a flattening can be stated as what it is: a change within one speaker,
    # needing no external reference.
    range_first_st: float | None = None
    range_last_st: float | None = None
    # The speaker's own middle, in Hertz. Reported so the semitone figures can
    # be read back into a frequency, never compared against anything.
    median_hz: float | None = None


def semitones(hz: float, reference_hz: float) -> float:
    """`hz` expressed as an interval from `reference_hz`."""
    return 12 * math.log2(hz / reference_hz)


def profile(contour: tuple[float | None, ...], per_utterance: tuple[tuple[float | None, ...], ...]) -> Profile:
    """Describe one call's pitch. `contour` is every frame in order,
    `per_utterance` the same frames grouped by utterance (for endings and movement).
    """
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
    """The 5th and 95th percentile of a set of voiced frames, in Hertz. Trimmed so
    one bad frame cannot decide the figure; shared by the span and the drawn band
    so the two cannot come apart.
    """
    if len(voiced) < MIN_VOICED_FRAMES:
        return None
    ordered = sorted(voiced)
    margin = len(ordered) // 20
    low, high = ordered[margin], ordered[-1 - margin]
    if low <= 0 or high < low:
        return None
    return low, high


def _range_st(voiced: list[float]) -> float | None:
    """That band as one figure: the spread from its bottom to its top."""
    band = _band(voiced)
    return None if band is None else round(semitones(band[1], band[0]), 2)


def _pvq(contour: tuple[float | None, ...]) -> tuple[float | None, int]:
    """The pitch variation quotient (Hincks 2005), and how many windows it came from.
    A short trailing remainder is dropped unless the call never filled a window --
    asked of the windows *seen*, not the quotients kept, or a long call whose
    windows all failed the voicing floor would be read off its remainder.
    """
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
    """How much the voice moves, in semitones per second of voiced speech.
    Per utterance then pooled, never across the flat call contour, where the seam
    between two utterances would count as movement the voice never made. Smoothed
    first (MOVEMENT_SMOOTH_FRAMES); steps over MAX_STEP_ST are octave errors.
    """
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
    # Per second, not per frame, so the figure does not change when the analysis
    # grid does.
    return round(sum(steps) / len(steps) * (1000 / STEP_MS), 2)


def _smooth(contour: tuple[float | None, ...]) -> tuple[float | None, ...]:
    """A median over MOVEMENT_SMOOTH_FRAMES (a mean would spread a stray frame
    instead of discarding it). Unvoiced frames stay unvoiced, so no gap is bridged.
    """
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
    """Read each utterance's final movement, over the last TERMINAL_WINDOW_MS of
    *voiced* frames (the recording itself usually ends unvoiced).
    """
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
    """The level threshold for the window this ending was actually read over.
    TERMINAL_FLAT_ST holds only for the full 400 ms; a short utterance's window
    needs a higher floor (4.6 ST at 70 ms), or inaudible movements count as
    falling/rising. `frames - 1`: the change is across intervals between frames.
    """
    return GLISSANDO_ST_S2 / (max(frames - 1, 1) * STEP_MS / 1000)


def _terminal_slope(utterance: tuple[float | None, ...]) -> tuple[float, int] | None:
    """The final movement of one utterance in semitones across the window
    (negative = falling), plus the window's frame count for `_flat_threshold_st`.
    A least-squares line end to end -- not endpoints (noisiest frames) and not
    two half-means, which silently halve every movement.
    """
    voiced = [hz for hz in utterance if hz]
    window = TERMINAL_WINDOW_MS // STEP_MS
    if len(voiced) < MIN_TERMINAL_FRAMES:
        return None
    tail = voiced[-window:]
    if len(tail) < MIN_TERMINAL_FRAMES:
        return None

    # In semitones relative to the tail's own start, so the fit is linear in the
    # scale the threshold is stated in.
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
    """The contour cut into three equal stretches of *voiced speech*, not of the
    clock, so a long silence cannot swallow a whole third.
    """
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
    """The grid `thin` will actually produce for a requested one (25 ms -> 20 ms).
    Anything stating the thinned grid must use this, not the request, or the
    drawing's axis claims a duration the curve does not have.
    """
    return _per_point(step_ms) * STEP_MS


def _per_point(step_ms: int) -> int:
    """How many analysis frames go into one thinned point."""
    return max(1, step_ms // STEP_MS)


def thin(contour: tuple[float | None, ...], step_ms: int) -> list[float | None]:
    """The contour at a coarser grid, for storage and drawing only (statistics
    use the full 10 ms). Median per window, so a stray frame is no spike; None
    for a window with no voicing.
    """
    per_point = _per_point(step_ms)
    out: list[float | None] = []
    for start in range(0, len(contour), per_point):
        window = [hz for hz in contour[start:start + per_point] if hz]
        out.append(round(_median(sorted(window)), 1) if window else None)
    return out


def utterance_breaks(
    per_utterance: tuple[tuple[float | None, ...], ...], step_ms: int
) -> list[int]:
    """Where one utterance ends and the next begins, as indices into the thinned
    curve, so a seam is not read as a movement of the voice. Empty utterances
    leave no mark; two in the same window collapse to one.
    """
    per_point = _per_point(step_ms)
    total = sum(len(utterance) for utterance in per_utterance)
    points = -(-total // per_point)  # the length `thin` will produce

    marks: list[int] = []
    frames = 0
    for utterance in per_utterance[:-1]:
        frames += len(utterance)
        index = frames // per_point
        if 0 < index < points and index not in marks:
            marks.append(index)
    return marks


# --- The reading, which is the one part of this module that judges -----------


class Liveliness(str, Enum):
    """How the PVQ is read on Hincks's three-step scale: an Einschätzung with its
    scale visible, never on the progress view (ADR 0065, 0077). Do not add a
    step between them -- that would be an invented boundary.
    """

    MONOTONE = "monotone"
    LIVELY = "lively"
    # Not "too much". The top step is where the liveliest speakers in Hincks's
    # corpus sat, not a point at which anything goes wrong, and the wording has
    # to stay clear of suggesting otherwise.
    VERY_LIVELY = "very_lively"


LABELS: dict[Liveliness, str] = {
    Liveliness.MONOTONE: "monoton",
    Liveliness.LIVELY: "lebendig",
    Liveliness.VERY_LIVELY: "sehr lebendig",
}

# The traffic light on each step (ADR 0078): it points, it does not grade. What
# each colour claims, as ADR 0078's sixth condition requires:
#   monotone     red     Look here first: on the phone a flat delivery costs emphasis.
#   lively       green   Nothing needs attention today (not "well done").
#   very_lively  yellow  NOT "too expressive": the figure is least trustworthy
#                        here (octave errors, nervousness) -- worth a look at the contour.
LIGHTS: dict[Liveliness, str] = {
    Liveliness.MONOTONE: "red",
    Liveliness.LIVELY: "green",
    Liveliness.VERY_LIVELY: "yellow",
}

# The upper bound of each step except the last. One table for the decision and
# the legend, so a recalibration moves both.
_LADDER: tuple[tuple[float, Liveliness], ...] = (
    (PVQ_MONOTONE_MAX, Liveliness.MONOTONE),
    (PVQ_LIVELY_MAX, Liveliness.LIVELY),
)

# The text behind the info icon, beside the thresholds it explains (ADR 0078).
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
    """The step a PVQ falls on, or None. No step below MIN_VOICED_MS_FOR_READING
    (`voiced_ms` None = not recorded, not withheld). A Session without a PVQ gets
    no step -- never derive one from the stored range, which would reinstate the
    withdrawn scale (ADR 0077).
    """
    if pvq is None:
        return None
    if voiced_ms is not None and voiced_ms < MIN_VOICED_MS_FOR_READING:
        return None
    for bound, step in _LADDER:
        if pvq < bound:
            return step
    return Liveliness.VERY_LIVELY


def liveliness_steps() -> list[dict[str, str | None]]:
    """The whole scale written out, in percent, so the interface can show what
    the step was read off. Built from the constants, with `light` served here
    rather than mapped in the frontend, so a recalibration reaches the legend.
    """
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
    """A threshold as the interface states it: 0.15 -> "15 %"."""
    return f"{value * 100:g} %"
