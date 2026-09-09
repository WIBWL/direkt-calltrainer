"""The shape of a speaker's pitch across a call (F-35).

Pure functions over the F0 contour `acoustics.py` measured: no audio, no
database, no model call.

One number was not enough, and that is the reason this module exists. A range
in semitones says how far the voice travelled between its extremes and nothing
about how it got there: a speaker who says one sentence brightly and mumbles the
rest can reach the same figure as one who is lively throughout, and a speaker
who ends every sentence on a rise reaches it the same way as one who closes
every sentence firmly. Those are different things to work on.

So the contour is described by four factors, and each one is chosen because it
is (a) readable off the contour without inventing a norm and (b) something a
speaker can actually do differently tomorrow:

    Umfang      how far the voice ranges, 5th to 95th percentile in semitones
    Bewegung    how much it moves per second of speech, semitones per second
    Satzenden   whether utterances end falling, rising or level
    Verlauf     whether the range widens or narrows across the call

Three of the four need no reference point outside the speaker. The fourth,
Satzenden, has a natural zero: a slope is rising or falling regardless of whose
voice it is, and what a final rise or fall conventionally signals is one of the
better-established findings about intonation. That is why the interpretation
this module supports is concentrated there, and why the other three are reported
as figures rather than as verdicts. ADR 0051 declined to invent norms for the
Kennzahlen; nothing here does either.

Everything is computed in semitones relative to the speaker's own median, which
is the standard normalisation in phonetics and the reason a low and a high voice
produce comparable numbers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

# The analysis grid the contour arrives on (backend/feedback/acoustics.py).
STEP_MS = 10

# How much of an utterance's end the terminal contour is read from. Long enough
# to span the final syllable or two, which is where a German intonation phrase
# places its nuclear movement, and short enough not to reach back into the
# sentence before it.
TERMINAL_WINDOW_MS = 400
# Below this slope an ending counts as level rather than as a movement. Two
# semitones over the final stretch is around the smallest interval a listener
# reliably hears as a direction rather than as wobble.
TERMINAL_FLAT_ST = 2.0
# A terminal contour needs this many voiced frames in its window to be read at
# all; below it the "slope" would be two points and a guess.
MIN_TERMINAL_FRAMES = 8

# A jump larger than this between neighbouring frames is not a voice, it is the
# tracker changing its mind. Excluded from the movement figure, which would
# otherwise be dominated by them.
MAX_STEP_ST = 6.0

# Below this many voiced frames a factor is not reported at all. Everything here
# is a shape, and a shape needs enough points to have one.
MIN_VOICED_FRAMES = 20

# The metric this module feeds, named here so the API, the tests and the
# interface agree on the string rather than each spelling it out.
RANGE_KEY = "intonation"

# --- The five-step reading -------------------------------------------------
# Where the Umfang is read as monotone, balanced or overdone, in semitones.
#
# Worth stating plainly, because the rest of this module is careful not to:
# THIS IS A JUDGEMENT, and ADR 0004/0051 rule judgements out for the Kennzahlen
# on the grounds that no threshold is validated for this population. It exists
# because it was asked for, it is confined to the single-call view, and it is
# removable by deleting this block, `liveliness`, `liveliness_steps` and the
# two places that call them.
#
# The numbers are not pulled out of the air, but they are not measured on this
# population either. They come from the F0 standard deviations usually reported
# for speech -- around 1 semitone for speech heard as monotone, 2 to 3 for
# ordinary conversation, 4 and above for animated delivery -- converted to the
# 5th-to-95th-percentile span this metric actually reports, which for a roughly
# normal distribution is about 3.3 standard deviations. That conversion is the
# whole derivation, and it is why the interface says "Einschätzung" and shows
# the scale: a reader who disagrees can see the boundary they are disagreeing
# with.
VERY_MONOTONE_MAX_ST = 4.0   # ~1.2 st SD
MONOTONE_MAX_ST = 7.0        # ~2.1 st SD
BALANCED_MAX_ST = 12.0       # ~3.6 st SD
LIVELY_MAX_ST = 18.0         # ~5.5 st SD, or an octave error the trim missed


class Ending(str, Enum):
    """How one utterance ended."""

    FALLING = "falling"
    RISING = "rising"
    LEVEL = "level"


@dataclass(frozen=True)
class Endings:
    """The terminal contours of a call, counted.

    The one factor here that carries a conventional meaning: a falling ending
    closes a statement, a rising one leaves it open or asks. Neither is good or
    bad on its own, which is why this is a count and not a score. What it is
    useful for is the mismatch: a speaker who ends every second statement on a
    rise sounds less certain than they are, and that is something they can hear
    once it is pointed out.
    """

    falling: int = 0
    rising: int = 0
    level: int = 0

    @property
    def total(self) -> int:
        """How many utterances were long enough to read an ending from."""
        return self.falling + self.rising + self.level


@dataclass(frozen=True)
class Profile:
    """The four factors, or as many of them as the contour supported."""

    # 5th to 95th percentile, in semitones. None below MIN_VOICED_FRAMES.
    range_st: float | None = None
    # Mean absolute change between neighbouring voiced frames, in semitones per
    # second of voiced speech.
    movement_st_per_s: float | None = None
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
    """Describe one call's pitch.

    `contour` is every voiced frame of the call in order, `per_utterance` the
    same frames grouped by utterance -- which the terminal contours need and the
    other three factors do not.
    """
    voiced = [hz for hz in contour if hz]
    if len(voiced) < MIN_VOICED_FRAMES:
        return Profile()

    median = _median(sorted(voiced))
    thirds = _thirds(contour)
    return Profile(
        range_st=_range_st(voiced),
        movement_st_per_s=_movement(contour),
        endings=_endings(per_utterance),
        range_first_st=_range_st([hz for hz in thirds[0] if hz]),
        range_last_st=_range_st([hz for hz in thirds[2] if hz]),
        median_hz=round(median, 1),
    )


def _range_st(voiced: list[float]) -> float | None:
    """The 5th to 95th percentile spread, in semitones.

    Trimmed rather than min-to-max: a single frame the tracker got wrong would
    otherwise decide the figure for the whole call. The trim is why the two-pass
    measurement in acoustics.py matters as well -- between them, an octave error
    has to survive both to reach this number.
    """
    if len(voiced) < MIN_VOICED_FRAMES:
        return None
    ordered = sorted(voiced)
    margin = len(ordered) // 20
    low, high = ordered[margin], ordered[-1 - margin]
    if low <= 0 or high < low:
        return None
    return round(semitones(high, low), 2)


def _movement(contour: tuple[float | None, ...]) -> float | None:
    """How much the voice moves, in semitones per second of voiced speech.

    The factor that separates a wide range from a lively one. A speaker can
    cover ten semitones by drifting slowly from a high start to a low finish,
    and cover the same ten by moving on every phrase; only this figure tells
    them apart.

    Steps larger than MAX_STEP_ST are dropped rather than counted: at 10 ms a
    real voice does not jump half an octave between frames, so such a step is
    the tracker and not the speaker.
    """
    steps: list[float] = []
    for before, after in zip(contour, contour[1:]):
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


def _endings(per_utterance: tuple[tuple[float | None, ...], ...]) -> Endings:
    """Read each utterance's final movement.

    The slope is taken over the last TERMINAL_WINDOW_MS of *voiced* frames, not
    the last frames of the recording: an utterance usually ends in a consonant
    or a breath, and those carry no pitch.
    """
    falling = rising = level = 0
    for utterance in per_utterance:
        movement = _terminal_slope(utterance)
        if movement is None:
            continue
        if movement <= -TERMINAL_FLAT_ST:
            falling += 1
        elif movement >= TERMINAL_FLAT_ST:
            rising += 1
        else:
            level += 1
    return Endings(falling=falling, rising=rising, level=level)


def _terminal_slope(utterance: tuple[float | None, ...]) -> float | None:
    """The final movement of one utterance, in semitones across the window.

    Negative is falling. A least-squares line through the tail, reported as the
    change that line predicts from one end of the window to the other, so the
    number means what it says: "the last 400 ms moved N semitones".

    A line rather than the difference of two endpoints, which are the noisiest
    frames in the tail, and rather than the difference of two half-means, which
    was the first attempt here and quietly halved every movement it measured:
    on a straight ramp the mean of the second half sits only half a window away
    from the mean of the first, so a four-semitone fall reported as two and the
    threshold below silently meant twice what it said.
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
    return round(slope * (count - 1), 2)


def _thirds(contour: tuple[float | None, ...]) -> tuple[tuple[float | None, ...], ...]:
    """The contour cut into three equal stretches of *voiced speech*.

    Of speech and not of the clock: the pauses between utterances belong to
    neither third, and a call with one long silence in the middle would
    otherwise put its whole second third inside that silence.
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


def thin(contour: tuple[float | None, ...], step_ms: int) -> list[float | None]:
    """The contour at a coarser grid, for storage and drawing.

    The statistics are computed on the full 10 ms contour; only the curve that
    goes into `detail_json` and onto the screen is thinned, because a three
    minute call at 10 ms is eighteen thousand points and no chart resolves them.

    Takes the median of each window rather than one sample from it, so a single
    stray frame does not become a visible spike, and yields None for a window
    with no voicing in it at all.
    """
    per_point = max(1, step_ms // STEP_MS)
    out: list[float | None] = []
    for start in range(0, len(contour), per_point):
        window = [hz for hz in contour[start:start + per_point] if hz]
        out.append(round(_median(sorted(window)), 1) if window else None)
    return out


# --- The reading, which is the one part of this module that judges -----------


class Liveliness(str, Enum):
    """How the Umfang is read on the five-step scale.

    Everything above this line describes; this describes and then decides, on
    two of the invented thresholds ADR 0051 declined to invent. It is presented
    as an Einschätzung with its scale visible, never as a measurement, and it
    is deliberately absent from the progress view (ADR 0065).
    """

    VERY_MONOTONE = "very_monotone"
    MONOTONE = "monotone"
    BALANCED = "balanced"
    LIVELY = "lively"
    # "Overdrawn" rather than "too much": the step above lively is either a very
    # expressive speaker or a tracking error, and both are worth a second look
    # rather than a correction.
    EXAGGERATED = "exaggerated"


LABELS: dict[Liveliness, str] = {
    Liveliness.VERY_MONOTONE: "stark monoton",
    Liveliness.MONOTONE: "monoton",
    Liveliness.BALANCED: "ausgewogen",
    Liveliness.LIVELY: "lebendig",
    Liveliness.EXAGGERATED: "überzeichnet",
}

# The text behind the info icon, beside the thresholds it explains.
EXPLANATION = (
    "Gemessen wird die Spanne zwischen Ihrem tiefsten und höchsten üblichen Ton "
    "(5. bis 95. Perzentil) in Halbtönen, bezogen auf Ihre eigene mittlere "
    "Stimmlage. In Halbtönen und nicht in Hertz, damit eine tiefe und eine hohe "
    "Stimme bei gleicher Lebendigkeit dieselbe Zahl ergeben. Die fünf Stufen "
    "sind aus den in der Literatur üblichen Streuungswerten gesprochener "
    "Sprache abgeleitet und für diese Nutzergruppe nicht validiert: eine "
    "Orientierung, kein Urteil. Wie viel Melodie angemessen ist, hängt außerdem "
    "vom Anlass ab — eine Reklamation klingt zu Recht anders als ein "
    "Verkaufsgespräch."
)


def liveliness(range_st: float | None) -> Liveliness | None:
    """The step a range falls on, or None where nothing was measured.

    On the range alone, deliberately. The movement figure is the better
    discriminator in principle -- a contour that drifts slowly from high to low
    covers ground without sounding lively -- but the range is the one of the two
    for which published figures exist to anchor a boundary. Reading the movement
    would mean inventing a second threshold with nothing behind it and hiding it
    inside a verdict, so it stays what it is: a factor reported beside the step,
    with the wording that tells the two apart.
    """
    if range_st is None:
        return None
    if range_st < VERY_MONOTONE_MAX_ST:
        return Liveliness.VERY_MONOTONE
    if range_st < MONOTONE_MAX_ST:
        return Liveliness.MONOTONE
    if range_st < BALANCED_MAX_ST:
        return Liveliness.BALANCED
    if range_st < LIVELY_MAX_ST:
        return Liveliness.LIVELY
    return Liveliness.EXAGGERATED


def liveliness_steps() -> list[dict[str, str | None]]:
    """The whole scale, written out, so the interface can show what the step
    was read off.

    Built from the constants rather than written twice: a recalibration has to
    reach the legend, or the user is shown a boundary that no longer decides
    anything. `light` is null throughout -- these steps carry no colour, because
    a scale that is bad at both ends cannot be drawn as a traffic light without
    claiming a direction it does not have.
    """
    bounds = [
        (Liveliness.VERY_MONOTONE, f"unter {_st(VERY_MONOTONE_MAX_ST)} Halbtönen"),
        (Liveliness.MONOTONE,
         f"{_st(VERY_MONOTONE_MAX_ST)} bis {_st(MONOTONE_MAX_ST)} Halbtöne"),
        (Liveliness.BALANCED,
         f"{_st(MONOTONE_MAX_ST)} bis {_st(BALANCED_MAX_ST)} Halbtöne"),
        (Liveliness.LIVELY,
         f"{_st(BALANCED_MAX_ST)} bis {_st(LIVELY_MAX_ST)} Halbtöne"),
        (Liveliness.EXAGGERATED, f"über {_st(LIVELY_MAX_ST)} Halbtönen"),
    ]
    return [
        {"step": step.value, "label": LABELS[step], "range": span, "light": None}
        for step, span in bounds
    ]


def _st(value: float) -> str:
    """A threshold as the interface states it: no decimal point on a whole one."""
    return f"{value:g}"
