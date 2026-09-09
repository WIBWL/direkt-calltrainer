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

# The movement figure is read off a contour smoothed over this many frames
# (30 ms), which is below the shortest thing a voice does deliberately and above
# the frame-to-frame wobble of the tracker.
#
# Measured, not assumed. On a synthetic contour with a 4.5 Hz syllable rate,
# adding 2% frame-to-frame noise -- which is what a tracker produces on a real
# voice, quite apart from the speaker's own jitter -- moved the unsmoothed
# figure from 46.3 to 59.7 semitones per second, a 29% inflation of a number
# that is supposed to describe intonation. At three frames the same noise costs
# 4.5%, while the movement actually present is only damped by 5%. Five frames
# were tried too and started eating the syllable-rate movement itself (-13%).
MOVEMENT_SMOOTH_FRAMES = 3

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

# How much voiced speech a step needs under it. The figure itself is reported
# from MIN_VOICED_FRAMES (0.2 s) upwards, because a spread is a spread; calling
# somebody monotone on that much material would be something else entirely. Ten
# seconds of voicing is roughly a minute of a normal call, given how much of
# speech carries no pitch at all and how much of a call the other side is
# talking.
MIN_VOICED_MS_FOR_READING = 10_000


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
    # The two ends of that span, each in semitones from the speaker's median.
    # Reported separately because they are *not* symmetric around it -- a voice
    # reaches further up than down, or the other way about -- and the drawn band
    # would otherwise be a guess dressed as a measurement.
    band_low_st: float | None = None
    band_high_st: float | None = None
    # Mean absolute change between neighbouring voiced frames, in semitones per
    # second of voiced speech.
    movement_st_per_s: float | None = None
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
    band = _band(voiced)
    return Profile(
        range_st=_range_st(voiced),
        band_low_st=None if band is None else round(semitones(band[0], median), 2),
        band_high_st=None if band is None else round(semitones(band[1], median), 2),
        movement_st_per_s=_movement(per_utterance or (contour,)),
        voiced_ms=len(voiced) * STEP_MS,
        endings=_endings(per_utterance),
        range_first_st=_range_st([hz for hz in thirds[0] if hz]),
        range_last_st=_range_st([hz for hz in thirds[2] if hz]),
        median_hz=round(median, 1),
    )


def _band(voiced: list[float]) -> tuple[float, float] | None:
    """The 5th and 95th percentile of a set of voiced frames, in Hertz.

    Trimmed rather than min-to-max: a single frame the tracker got wrong would
    otherwise decide the figure for the whole call. The trim is why the two-pass
    measurement in acoustics.py matters as well -- between them, an octave error
    has to survive both to reach this number.

    One implementation for the span and for the two ends of it, so the figure
    and the band drawn behind the contour cannot come apart.
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


def _movement(per_utterance: tuple[tuple[float | None, ...], ...]) -> float | None:
    """How much the voice moves, in semitones per second of voiced speech.

    The factor that separates a wide range from a lively one. A speaker can
    cover ten semitones by drifting slowly from a high start to a low finish,
    and cover the same ten by moving on every phrase; only this figure tells
    them apart.

    Per utterance and then pooled, never across the whole call at once. The
    call's contour is the speaker's utterances laid end to end with the
    Persona's turns removed, so the last frame of one utterance and the first
    frame of the next sit next to each other with a minute of somebody else's
    speech between them in reality. Counted as a step, that is movement the
    voice never made.

    Two filters, and they catch different things. The 30 ms median below removes
    the tracker's frame-to-frame wobble, which otherwise inflates the figure by
    a third on a noisy recording (see MOVEMENT_SMOOTH_FRAMES). Steps larger than
    MAX_STEP_ST are then dropped as octave errors: at 10 ms no real voice jumps
    half an octave.
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
    """A median over MOVEMENT_SMOOTH_FRAMES, with the gaps left where they are.

    The median and not a mean: a mean would spread a single stray frame over its
    neighbours instead of discarding it, which is the opposite of the point.
    Unvoiced frames stay unvoiced -- smoothing a gap shut would connect two
    stretches that were never connected.
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


def effective_step_ms(step_ms: int) -> int:
    """The grid `thin` will actually produce for a requested one.

    Thinning works in whole analysis frames, so a request for 25 ms yields
    20 ms. Everything that states or measures the thinned grid -- the axis of
    the drawing, the seam indices, the figure in the payload -- has to use this
    and not the number that was asked for, or the drawing claims a duration the
    curve does not have (a 19 second contour labelled 24 seconds, which is how
    this was found).
    """
    return _per_point(step_ms) * STEP_MS


def _per_point(step_ms: int) -> int:
    """How many analysis frames go into one thinned point."""
    return max(1, step_ms // STEP_MS)


def thin(contour: tuple[float | None, ...], step_ms: int) -> list[float | None]:
    """The contour at a coarser grid, for storage and drawing.

    The statistics are computed on the full 10 ms contour; only the curve that
    goes into `detail_json` and onto the screen is thinned, because a three
    minute call at 10 ms is eighteen thousand points and no chart resolves them.

    Takes the median of each window rather than one sample from it, so a single
    stray frame does not become a visible spike, and yields None for a window
    with no voicing in it at all.
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
    """Where one of the speaker's utterances ends and the next begins, as
    indices into the thinned curve.

    The curve holds the user's frames only, one utterance after the other, with
    the Persona's turns not represented at all -- that is what makes the
    horizontal axis speaking time rather than call time. Without these marks a
    reader would take a seam between two utterances for a movement of the voice.
    Each index is therefore *both* an end and the next start, and the interface
    draws it as one line rather than as a gap.

    Empty utterances (no voicing measured at all) contribute nothing to the
    curve and so cannot be marked on it; two very short utterances landing in
    the same window collapse to one mark rather than being drawn twice.
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

# The upper bound of each step except the last, in the order they are read and
# shown. One table for the decision and for the legend, so a recalibration
# cannot move a boundary in one and leave it in the other.
_LADDER: tuple[tuple[float, Liveliness], ...] = (
    (VERY_MONOTONE_MAX_ST, Liveliness.VERY_MONOTONE),
    (MONOTONE_MAX_ST, Liveliness.MONOTONE),
    (BALANCED_MAX_ST, Liveliness.BALANCED),
    (LIVELY_MAX_ST, Liveliness.LIVELY),
)

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


def liveliness(range_st: float | None, voiced_ms: int | None = None) -> Liveliness | None:
    """The step a range falls on, or None where nothing was measured.

    `voiced_ms` is how much voiced speech the range came from; below
    MIN_VOICED_MS_FOR_READING there is no step, only the figure. None means the
    Session did not record it, which is treated as "no reason to withhold" --
    the figure was measured under the same rules either way.

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
    if voiced_ms is not None and voiced_ms < MIN_VOICED_MS_FOR_READING:
        return None
    for bound, step in _LADDER:
        if range_st < bound:
            return step
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
    spans: list[tuple[Liveliness, str]] = []
    floor: float | None = None
    for bound, step in _LADDER:
        spans.append((step, f"unter {_st(bound)} Halbtönen" if floor is None
                      else f"{_st(floor)} bis {_st(bound)} Halbtöne"))
        floor = bound
    spans.append((Liveliness.EXAGGERATED, f"über {_st(floor)} Halbtönen"))
    return [
        {"step": step.value, "label": LABELS[step], "range": span, "light": None}
        for step, span in spans
    ]


def _st(value: float) -> str:
    """A threshold as the interface states it: no decimal point on a whole one."""
    return f"{value:g}"
