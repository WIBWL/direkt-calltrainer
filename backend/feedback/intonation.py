"""The shape of a speaker's pitch across a call (F-35).

Pure functions over the F0 contour `acoustics.py` measured: no audio, no
database, no model call.

One number was not enough, and that is the reason this module exists. A range
in semitones says how far the voice travelled between its extremes and nothing
about how it got there: a speaker who says one sentence brightly and mumbles the
rest can reach the same figure as one who is lively throughout, and a speaker
who ends every sentence on a rise reaches it the same way as one who closes
every sentence firmly. Those are different things to work on.

So the contour is described by five figures, and each one is chosen because it
is (a) readable off the contour without inventing a norm and (b) something a
speaker can actually do differently tomorrow:

    range        how far the voice ranges, 5th to 95th percentile in semitones
    Bewegung      how much it moves per second of speech, semitones per second
    liveliness  the pitch variation quotient: SD/mean of F0 per 10 s window
    Satzenden     whether utterances end falling, rising or level
    Verlauf       whether the range widens or narrows across the call

Three of the five need no reference point outside the speaker. The other two do,
and it is worth being exact about how good those reference points are, because
that is what decides how far this module is allowed to interpret.

Satzenden has a natural zero: a slope rises or falls regardless of whose voice
it is, and the floor below which a movement is not heard as a movement at all is
a measured perceptual threshold rather than a chosen one -- see TERMINAL_FLAT_ST
and the glissando threshold it comes from.

liveliness is the only figure here with published boundaries behind it, and
that is why the reading at the foot of this module rests on it and no longer on
the range. Hincks (2005) measured the pitch variation quotient against human
liveliness ratings and reports where monotone ends and lively begins. Those
boundaries were established on 18 Swedish students presenting in L2 English in a
classroom, which is neither this population nor this channel; the module carries
that caveat to every place the step is shown rather than dropping it after the
first mention.

Everything else is in semitones relative to the speaker's own median. That is
the standard normalisation in phonetics and the reason a low and a high voice
produce comparable numbers -- and it is the better-supported choice, not merely
the conventional one. Nolan (2003) had listeners imitate intonation spans across
male and female voices: semitones and ERB-rate both beat Hertz, Mel and Bark by
a wide margin, and semitones came out slightly ahead of ERB-rate (relative error
31%/21% for male/female listeners against 35%/25% for ERB and 40%/43% for Hertz).
The ERB-rate scale that Hermes & van Gestel (1991) preferred for judgements of
*prominence* does not win on span, which is what this module measures.

What is deliberately not attempted here, and would be the next real improvement:
Prosogram-style stylisation of the whole contour (Mertens 2004), which replaces
every sub-threshold movement with a level tone before anything is counted. It
cannot be done in this module as it stands, because it is defined over vowel
nuclei -- segmented from the intensity peak, -3 dB to the left and -9 dB to the
right -- and the intensity curve lives in acoustics.py on a different grid and
is not carried alongside the pitch. The terminal contour below is the one place
where the segment is already known, so it is the one place the threshold is
applied honestly.
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

# The glissando threshold: below this rate of change, a pitch movement lasting
# T seconds is not heard as a movement at all, only as a level tone. In
# semitones per second, as G = GLISSANDO_ST_S2 / T**2.
#
# 0.32 and not the 0.16 usually quoted. Both figures are in the literature and
# the difference is not a rounding: 0.16 was established on isolated vowels
# ('t Hart 1976), and Mertens & d'Alessandro found that carrying it over to
# running speech keeps a great many intra-syllabic glides that no listener
# actually hears. The doubled threshold is what reproduces expert transcriptions
# of continuous speech and is what Prosogram uses (Mertens 2004). This module
# measures continuous speech.
GLISSANDO_ST_S2 = 0.32

# Below this total movement an ending counts as level rather than as a
# direction. Derived rather than chosen: the glissando threshold over a window
# of T seconds is GLISSANDO_ST_S2 / T**2 semitones per second, so across the
# window itself it comes to GLISSANDO_ST_S2 / T semitones -- 0.8 over 400 ms.
#
# This replaces a hand-set 2.0, which was 2.5 times the perceptual threshold and
# therefore filed a good many endings as level that a listener hears as falling
# or rising. Worth knowing about the change: it cannot be checked against the
# stored Sessions, because the terminal slope needs the 10 ms contour and only
# the thinned curve is kept (ADR 0048). It is a better-founded number, not a
# verified one, and the counts it produces are worth eyeballing on the first
# real calls after it ships.
TERMINAL_FLAT_ST = round(GLISSANDO_ST_S2 / (TERMINAL_WINDOW_MS / 1000), 2)
# A terminal contour needs this many voiced frames in its window to be read at
# all; below it the "slope" would be two points and a guess.
MIN_TERMINAL_FRAMES = 8

# A jump larger than this between neighbouring frames is not a voice, it is the
# tracker changing its mind. Excluded from the movement figure, which would
# otherwise be dominated by them.
#
# A heuristic, and stated as one: it is a plausibility bound on the tracker, not
# a perceptual threshold. The audibility figures in the literature -- the
# glissando threshold above, and the differential glissando threshold of 20 ST/s
# for hearing a *change* of slope -- answer a different question, namely which
# movements a listener notices, and neither of them rules a frame out as a
# measurement error.
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

# --- The pitch variation quotient -------------------------------------------
# Hincks (2005): the standard deviation of F0 divided by its mean, computed over
# a window of speech rather than over the whole recording, and in Hertz rather
# than in semitones. The unit looks like the wrong one for this module and is
# not: a quotient of two frequencies is dimensionless, so it normalises across
# voices by construction, the same job the semitone conversion does elsewhere.
# Following her definition exactly is the point -- it is what makes the
# boundaries below apply to this figure at all.
PVQ_WINDOW_MS = 10_000

# How much of a window has to carry voicing for that window to be usable.
#
# This is a floor of ours and not Hincks's. Hers is "no more than 4 seconds of
# pause in the 10 seconds", which cannot be applied here: the contour this module
# receives is the user's utterances laid end to end with the Persona's turns and
# the silence between utterances already removed, so the pauses her rule counts
# are largely not in it. What is left to guard against is a window that is nearly
# all unvoiced -- consonants, breath, a trailing whisper -- and 30% is a lenient
# bound on that, well under the voiced share of ordinary speech.
MIN_VOICED_SHARE_IN_WINDOW = 0.3

# The metric this module feeds, named here so the API, the tests and the
# interface agree on the string rather than each spelling it out.
RANGE_KEY = "intonation"

# --- The three-step reading -------------------------------------------------
# Where the pitch variation quotient is read as monotone or lively.
#
# Worth stating plainly, because the rest of this module is careful not to:
# THIS IS A JUDGEMENT, and ADR 0004/0051 rule judgements out for the metrics
# on the grounds that no threshold is validated for this population. It exists
# because it was asked for, it is confined to the single-call view, and it is
# removable by deleting this block, `liveliness`, `liveliness_steps` and the
# two places that call them.
#
# What changed, and why it is worth recording here rather than only in the
# history: this reading used to sit on the range, on five steps whose
# boundaries were derived by taking the F0 standard deviations usually quoted
# for speech and converting them to a 5th-to-95th-percentile span through a
# factor of about 3.3. A literature review of that derivation found nothing
# behind either half of it -- no source in the reviewed set states the span
# figures, none states the distribution of log F0 that the conversion assumes,
# and none reports either for German. It was two guesses stacked on each other
# wearing a citation.
#
# Hincks (2005) is the closest thing to a measured boundary that exists for
# this: the pitch variation quotient computed over 10-second windows, read
# against the liveliness ratings of human listeners, with the mean of 9 such
# windows correlating at r = 0.83 with those ratings. So the reading moves onto
# the figure that has the evidence and off the one that does not, while the
# range stays what it always was -- the metric's headline number, reported
# without a verdict.
#
# The caveat that remains, and it is not small: those boundaries come from 18
# Swedish students giving classroom presentations in L2 English, recorded on a
# room microphone. This is German, spontaneous, adversarial at times, and over a
# telephone band that cuts below 300 Hz. Whether the figures transfer is not
# addressed by any source reviewed. Hence "Einschätzung" in the interface, the
# visible scale, and the sentence about where the numbers come from.
PVQ_MONOTONE_MAX = 0.15
PVQ_LIVELY_MAX = 0.25

# How much voiced speech a step needs under it. The figure itself is reported
# from MIN_VOICED_FRAMES (0.2 s) upwards, because a spread is a spread; calling
# somebody monotone on that much material would be something else entirely. Ten
# seconds of voicing is roughly a minute of a normal call, given how much of
# speech carries no pitch at all and how much of a call the other side is
# talking -- which puts it at two to three of Hincks's windows, against the nine
# her reliability figure rests on. A floor, then, and not a sufficiency.
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
class Profile:  # pylint: disable=too-many-instance-attributes  # a record of measurements
    """The five figures, or as many of them as the contour supported.

    Eleven fields for five figures, because three of them are reported with the
    material they rest on -- the band with both its ends, the quotient with its
    window count -- and a figure whose basis is not carried beside it invites
    being read as firmer than it is.
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


def _pvq(contour: tuple[float | None, ...]) -> tuple[float | None, int]:
    """The pitch variation quotient, and how many windows it was read from.

    Hincks (2005)'s measure, kept to her definition because the boundaries in
    `liveliness` only apply to something computed the way she computed it: the
    standard deviation of F0 over its mean, in Hertz, over a window of speech,
    with the windows then averaged.

    Windowed and not taken over the call at once, and that is what the measure
    is for. A quotient over the whole contour counts the drift between one
    utterance and the next as though it were variation inside a sentence, so a
    speaker who opened high and finished low reads as lively without ever having
    moved within a phrase. Ten seconds is short enough to sit inside the
    speaker's current register and long enough to hold several phrases.

    A trailing remainder shorter than a full window is dropped, since a quotient
    over three seconds is not the same statistic and averaging it in with the
    others would quietly weight the end of the call. The exception is a call too
    short to fill one window at all, which is measured whole rather than not at
    all -- the reading has its own floor (MIN_VOICED_MS_FOR_READING) and will
    withhold a step from it anyway.
    """
    per_window = PVQ_WINDOW_MS // STEP_MS
    quotients: list[float] = []
    for start in range(0, len(contour), per_window):
        window = contour[start:start + per_window]
        if len(window) < per_window and quotients:
            break
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
    """How the pitch variation quotient is read on the three-step scale.

    Everything above this line describes; this describes and then decides, on
    thresholds ADR 0051 declined to invent. It is presented as an Einschätzung
    with its scale visible, never as a measurement, and it is deliberately
    absent from the progress view (ADR 0065).

    Three steps and not the five this used to have. The five came from a scale
    built here; these three are the ones Hincks reports, and inventing a fourth
    boundary to sit between them would put back exactly what the review took
    out.
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

# The traffic light on each step, governed by ADR 0078.
#
# It exists so a reader gets an impression of the call before the reading
# starts: the wrap-up hands them nine figures at equal weight, and colour is the
# only channel on that screen that says which one to look at first. It points,
# it does not grade. Green means nothing here needs attention today, not "well
# done"; red means look here first, not "you did badly".
#
# ADR 0078's conditions, and where each is met: the colour sits on the
# classification and never on the semitone figure (`api/sessions.py`), the whole
# scale travels with it in percent (`liveliness_steps`), the step is always
# written out in words (`LABELS`), the caveat names the population the
# boundaries came from (`EXPLANATION`), colour and wording are served from here
# beside the threshold, and none of it reaches the progress view (ADR 0065).
#
# What the three colours are claiming, written out because ADR 0078's sixth
# condition requires it: a traffic light asserts a direction whether or not one
# was intended, so the assertion is made explicit and can be argued with.
#
#   monotone       red     Look here first. The end F-35 exists to make
#                          visible, and the one step where something is
#                          reliably harder for the listener: on the telephone,
#                          with no face to read, a flat delivery costs the
#                          emphasis that carries the meaning.
#   lively         green   Nothing here needs attention today. Where Hincks's
#                          listeners heard ordinary, engaged speech.
#   very_lively    yellow  NOT a claim that expressiveness is a fault. Nothing
#                          reviewed supports that, and above 0.25 is simply
#                          where the liveliest speakers in her corpus sat. The
#                          yellow marks the one region where the *figure* is
#                          least trustworthy: an octave error inflates a
#                          standard deviation badly, and high variation is also
#                          what nervousness and disfluency produce. It means
#                          "worth a look at the contour", and the wording says
#                          exactly that rather than leaving the colour to imply
#                          something harsher.
#
# Removing the light is deleting this table, the `light` line in
# `liveliness_steps`, and the two lines that read it in the frontend.
LIGHTS: dict[Liveliness, str] = {
    Liveliness.MONOTONE: "red",
    Liveliness.LIVELY: "green",
    Liveliness.VERY_LIVELY: "yellow",
}

# The upper bound of each step except the last, in the order they are read and
# shown. One table for the decision and for the legend, so a recalibration
# cannot move a boundary in one and leave it in the other.
_LADDER: tuple[tuple[float, Liveliness], ...] = (
    (PVQ_MONOTONE_MAX, Liveliness.MONOTONE),
    (PVQ_LIVELY_MAX, Liveliness.LIVELY),
)

# The text behind the info icon, beside the thresholds it explains. Plain
# German and no dashes, because it is read by someone who has just finished a
# call and wants to know what the colour on their screen means.
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
    """The step a pitch variation quotient falls on, or None where there is none.

    `voiced_ms` is how much voiced speech the figure came from; below
    MIN_VOICED_MS_FOR_READING there is no step, only the figure. None means the
    Session did not record it, which is treated as "no reason to withhold" --
    the figure was measured under the same rules either way.

    On the quotient and on nothing else, which is a change from reading it off
    the range, and the reason is that the range has no published boundary and
    this does. The other four figures stay what they were: reported beside the
    step, uninterpreted, each of them saying something the step cannot. In
    particular the movement figure is the better discriminator in principle -- a
    contour drifting slowly from high to low covers ground without sounding
    lively -- but no source reviewed anchors a boundary for it, so reading it
    would mean inventing a threshold and hiding it inside a verdict.

    A Session measured before the quotient existed passes None here and gets no
    step. That is deliberate: the old five-step reading was withdrawn because
    its derivation did not hold up, and back-filling it from the stored range
    would be reinstating it under a new name.
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
    """The whole scale, written out, so the interface can show what the step
    was read off.

    Built from the constants rather than written twice: a recalibration has to
    reach the legend, or the user is shown a boundary that no longer decides
    anything. The same goes for `light`, which is why it is served from here
    beside the threshold it belongs to rather than mapped in the frontend.

    Stated in percent, because that is what the quotient is: a standard
    deviation as a share of the mean it was taken around. "15 %" is a true
    reading of 0.15 and a legible one; the raw ratio is neither.
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
