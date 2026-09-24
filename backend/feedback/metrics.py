"""The MetricType inventory and the derivation of a Session's Measurement rows.
One entry per metric holds its seed data (provision.py) and its derivation, so
adding a metric is one `MetricDef`. Every metric describes the whole call
(ADR 0051); an inactive one has no `derive`. Knows nothing about Praat.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from statistics import fmean

from backend.db.models import ASPECT_HOW, ASPECT_WHAT
from backend.feedback import hesitations, intonation
from backend.feedback.calls import Conversation
from backend.feedback.interruptions import classify
from backend.session.language_packs import LANGUAGE_PACKS, LanguagePack

_MS_PER_MINUTE = 60_000
_MS_PER_SECOND = 1000

# The metric key `_run_length` feeds, named here so the API and the tests agree
# on the string rather than each spelling it out.
RUN_LENGTH_KEY = "run_length"

# The text behind this metric's "i" used to sit here. It moved to
# `explanations.py` when twelve more were written -- this module is near
# pylint's line ceiling, and the prose is read by a user while everything else
# here is arithmetic.

# Words, for rate denominators: letter runs, so punctuation and the digits STT
# writes for numbers don't inflate the count.
_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)
_SENTENCE_END_RE = re.compile(r"[.!?]+")
# The same, minus the question mark: a segment a question mark already ended.
_SENTENCE_SPLIT_RE = re.compile(r"[.!]+")
# The one metric the wrap-up reads as a course rather than as a figure, so
# generator.py has to be able to pick it out of the inventory by name.
LOUDNESS_KEY = "loudness"
# How many audible samples the dynamic range needs before it is a range rather
# than the distance between two samples. See `_loudness`: below twenty the 5th
# to 95th percentile trims nothing at all.
_MIN_LOUDNESS_POINTS = 20

# The stored pitch curve's grid. Not the loudness curve's 100 ms, which aliases
# the syllable rate into a sawtooth (measured). 50 ms is a whole number of
# analysis frames (see `effective_step_ms`); about 25 KB for a long call.
PITCH_INTERVAL_MS = 50


@dataclass(frozen=True)
class Measurement:
    """One Measurement to be written against a Session: a value plus ADR 0029's detail."""

    key: str
    value: float
    detail: dict | None = None


# A deriver sees the whole call and returns its metric's measurement -- or None
# when the call gave it nothing to measure.
Deriver = Callable[[Conversation], "Measurement | None"]


@dataclass(frozen=True)
class MetricDef:
    """One row of the metric_type reference table, plus how to compute and judge it."""

    key: str
    name: str
    unit: str | None
    # ASPECT_HOW or ASPECT_WHAT: which half of the metrics grid this one
    # sits in. A display grouping -- it never reaches the wrap-up prompt.
    aspect: str
    feature_id: str
    active: bool
    derive: Deriver | None = None


def measure(call: Conversation) -> list[Measurement]:
    """Derive every active metric for one finished Session. A metric that cannot
    be computed is absent, never a stand-in zero that reads as a measurement.
    """
    derived = (metric.derive(call) for metric in METRICS if metric.derive)
    return [m for m in derived if m is not None]


# --- Derivations ----------------------------------------------------------


def _talk_share(call: Conversation) -> Measurement | None:
    """F-24. The user's share of the speaking time (not wall-clock, so latency
    counts for neither side). Audio duration on both sides: phonation would
    strip the user's silences but not the Persona's.
    """
    spoken = call.user_speech_ms + call.persona_speech_ms
    # Words with no measured speaking time behind them mean the measurement
    # failed (ADR 0048), not that the speaker stayed silent. Reporting the
    # share anyway would put a 0% or a 100% in front of the user as though it
    # had been measured -- exactly what `measure` refuses to do elsewhere.
    if not call.user_acoustics_complete or not spoken:
        return None
    if call.user_text and not call.user_speech_ms:
        return None
    return Measurement(
        "talk_share",
        call.user_speech_ms * 100 / spoken,
        {"user_ms": call.user_speech_ms, "persona_ms": call.persona_speech_ms},
    )


def _questions(call: Conversation) -> Measurement | None:
    """F-41. Questions the user asked, counted from the transcript's question
    marks (a keyword list would miss German inversions). The open/closed split in
    the detail is read off the same marks, so it always adds up.
    """
    words = _count_words(call.user_text)
    if not words:
        return None
    questions = call.user_text.count("?")
    detail: dict = {"per_100_words": questions * 100 / words}
    pack = _pack(call)
    if pack and questions:
        opened = _open_questions(call.user_text, pack)
        detail |= {"open": opened, "closed": questions - opened}
    return Measurement("questions", float(questions), detail)


def _fillers(call: Conversation) -> Measurement | None:
    """F-51. Lexical fillers ("quasi", "sozusagen") counted in the transcript.

    Hesitation sounds are not among them: Whisper drops them, so a zero here
    says nothing about "äh". The detail names the words, most frequent first.
    """
    pack = _pack(call)
    words = _count_words(call.user_text)
    if not pack or not words:
        return None
    # Lowered and with runs of whitespace closed, so "Sag  ich mal" is counted
    # as the same phrase as "sag ich mal".
    found = Counter(" ".join(hit.lower().split()) for hit in pack.filler_re.findall(call.user_text))
    count = sum(found.values())
    return Measurement(
        "fillers",
        float(count),
        {"per_100_words": count * 100 / words, "words": dict(found.most_common())},
    )


def _repetitions(call: Conversation) -> Measurement | None:
    """F-08. Passages the user said again, word for word, later in the call.

    Overlapping matches merge, so one repeated sentence counts once. The detail
    quotes them, so a reader can see what was counted.
    """
    words = _WORD_RE.findall(call.user_text)
    if not words:
        return None
    passages = _repeated_passages(words)
    repeated = sum(len(passage.split()) for passage in passages)
    return Measurement(
        "repetitions",
        float(len(passages)),
        {"share_of_words": repeated * 100 / len(words), "passages": passages[:5]},
    )


# Four words, so a repeated "ich habe das" is no repetition but a repeated
# sentence is.
_REPEAT_WORDS = 4


def _repeated_passages(words: list[str]) -> list[str]:
    """The stretches of `words` that repeat an earlier one of _REPEAT_WORDS or more."""
    folded = [word.lower() for word in words]
    first_seen: dict[tuple[str, ...], int] = {}
    covered = [False] * len(words)
    for index in range(len(words) - _REPEAT_WORDS + 1):
        gram = tuple(folded[index:index + _REPEAT_WORDS])
        first = first_seen.setdefault(gram, index)
        # Only a later, non-overlapping occurrence: "ja ja ja ja ja" matching
        # itself is stammering, not saying something twice.
        if first + _REPEAT_WORDS <= index:
            covered[index:index + _REPEAT_WORDS] = [True] * _REPEAT_WORDS
    passages: list[str] = []
    span: list[str] = []
    for word, hit in zip(words, covered):
        if hit:
            span.append(word)
        elif span:
            passages.append(" ".join(span))
            span = []
    if span:
        passages.append(" ".join(span))
    return passages


def _hesitations(call: Conversation) -> Measurement | None:
    """F-51. Hesitation sounds, estimated from the pitch contour (hesitations.py).

    Absent when a Turn's acoustics failed: its contour is missing, and the count
    would be short by an unknown amount (ADR 0048).
    """
    if not call.user_acoustics_complete or not call.pitch_per_turn:
        return None
    # Each hold with the utterance it sits in, so the page can quote the
    # sentence (a located event, like `_pauses`). `index` matches the stored
    # transcript's order because an unmeasured utterance returned above.
    found = [
        {"turn": index, "start_ms": hold.start_ms, "duration_ms": hold.duration_ms}
        for index, turn in enumerate(call.pitch_per_turn)
        for hold in hesitations.holds(turn)
    ]
    return Measurement(
        "hesitations",
        float(len(found)),
        {
            "total_ms": sum(int(hold["duration_ms"]) for hold in found),
            "holds": found,
        },
    )


# Below these the opening's tempo is not compared: a handful of words gives a
# rate, not a tempo.
_MIN_OPENING_WORDS = 4
_MIN_REST_WORDS = 15


def _opening(call: Conversation) -> Measurement | None:
    """F-63. Whether the user's first turn greets, names them and offers help (or,
    when they rang, states the concern), plus its tempo against the rest. A bare
    name goes unrecognised: the screen says "nicht erkannt", never "fehlt".
    """
    pack = _pack(call)
    if not pack or not call.user_turns:
        return None
    found = opening_parts(call.user_turns[0][0], pack, reverse=call.reverse)
    return Measurement(
        "opening", float(sum(found.values())), found | {"pace_ratio": _opening_pace(call)}
    )


def opening_parts(first_text: str, pack: LanguagePack, *, reverse: bool) -> dict[str, bool]:
    """The three parts of an opening, found in the user's first utterance. Also
    run by `scripts/backfill_opening.py`, since words alone decide them. Whoever
    rang decides the third part and nothing else (ADR 0070/0086).
    """
    return {
        "greeting": bool(pack.greeting_re.search(first_text)),
        "name": bool(pack.self_intro_re.search(first_text)),
        # Stored under its own key, so the screen can name the part checked.
        ("concern" if reverse else "offer"): bool(
            (pack.concern_re if reverse else pack.offer_re).search(first_text)
        ),
    }


def _opening_pace(call: Conversation) -> float | None:
    """The first turn's words per phonated minute over the rest's, or None."""
    if not call.user_acoustics_complete or not _silence_found(call):
        return None
    (first, first_ms), rest = call.user_turns[0], call.user_turns[1:]
    first_words = _count_words(first)
    rest_words = sum(_count_words(text) for text, _ in rest)
    rest_ms = sum(ms for _, ms in rest)
    enough = first_words >= _MIN_OPENING_WORDS and rest_words >= _MIN_REST_WORDS
    if not enough or not first_ms or not rest_ms:
        return None
    return (first_words / first_ms) / (rest_words / rest_ms)


CLOSING_KEY = "closing"

# The closing is read in the user's last this-many turns (ADR 0089): the recap
# usually comes a turn before the goodbye, and three would be a third of a call
# this length.
CLOSING_WINDOW = 2

# Below this many user turns there is no closing to speak of, and the window
# would reach back into the opening. The same floor below which the post-call
# screen offers neither a follow-up nor a reverse (`MIN_USER_TURNS` in
# FeedbackView.tsx): a call hung up after a sentence or two has no end of its own.
MIN_CLOSING_TURNS = 3


def closing_parts(user_texts: Sequence[str], pack: LanguagePack) -> dict[str, bool] | None:
    """The three parts of a closing, found in the last `CLOSING_WINDOW` of
    `user_texts`, or None when there are too few turns. Also run by
    `scripts/backfill_closing.py`, since words alone decide them.
    """
    if len(user_texts) < MIN_CLOSING_TURNS:
        return None
    window = " ".join(user_texts[-CLOSING_WINDOW:])
    return {
        "recap": bool(pack.recap_re.search(window)),
        "agreement": bool(pack.agreement_re.search(window)),
        "farewell": bool(pack.sign_off_re.search(window)),
    }


def closing_measurement(parts: dict[str, bool]) -> Measurement:
    """The stored shape: how many parts were recognised, the parts themselves,
    and how many turns were read, so the screen can say where it looked with the
    backend's own number rather than a copy of it."""
    return Measurement(
        CLOSING_KEY, float(sum(parts.values())), parts | {"turns_read": CLOSING_WINDOW}
    )


def _closing(call: Conversation) -> Measurement | None:
    """ADR 0089. Whether the user's last two turns recap, name a concrete next
    step and say goodbye -- the same parts whoever rang. Unmatched wording reads
    "nicht erkannt", never "fehlt", as for the opening.
    """
    pack = _pack(call)
    if not pack:
        return None
    parts = closing_parts([text for text, _ in call.user_turns], pack)
    return closing_measurement(parts) if parts is not None else None


def _open_questions(text: str, pack: LanguagePack) -> int:
    """How many of the question marks in `text` end an open question.

    Only the last clause of a segment is the question; what precedes the
    nearest full stop belongs to the sentence before it.
    """
    return sum(
        1 for segment in text.split("?")[:-1]
        if pack.open_question_re.match(_SENTENCE_SPLIT_RE.split(segment)[-1].strip())
    )


def _pace(call: Conversation) -> Measurement | None:
    """F-36. Words per minute of phonation (VAD padding and inner silences
    excluded). Never relative to the Persona: its rate is a TTS setting, not the
    user (ADR 0051).
    """
    words = _count_words(call.user_text)
    measurable = call.user_acoustics_complete and call.user_phonation_ms and _silence_found(call)
    if not words or not measurable:
        return None
    # The two terms, so the page can show the division. Whole call only: a tempo
    # per Turn is a per-utterance statistic, which ADR 0051 rules out.
    return Measurement(
        "pace",
        words * _MS_PER_MINUTE / call.user_phonation_ms,
        {"words": words, "phonation_ms": call.user_phonation_ms},
    )


def _word_count(call: Conversation) -> Measurement | None:
    """F-08. How much the user said in total, with sentence length alongside it
    as the observable trace of an over-packed explanation. Whether it actually
    was one is a judgment for the wrap-up, not for this number."""
    words = _count_words(call.user_text)
    if not words:
        return None
    sentences = [s for s in _SENTENCE_END_RE.split(call.user_text) if _count_words(s)]
    return Measurement(
        "word_count",
        float(words),
        {"sentence_count": len(sentences), "words_per_sentence": words / len(sentences) if sentences else None},
    )


def _reaction_time(call: Conversation) -> Measurement | None:
    """F-53. Average seconds between the Persona falling silent and the user
    starting to speak. The model's own thinking and speaking time falls outside
    this window by construction, so a slow gateway cannot read as hesitation."""
    if not call.reactions:
        return None
    gaps = [reaction.gap_ms for reaction in call.reactions]
    return Measurement(
        "reaction_time",
        fmean(gaps) / _MS_PER_SECOND,
        {
            "longest_s": max(gaps) / _MS_PER_SECOND,
            "count": len(gaps),
            # Each silence with the reply it stood in front of, so the page can
            # show the exchange instead of a bare average. Located events, the
            # shape `_pauses` and F-51's interruption offsets already store --
            # not a statistic per Turn, which ADR 0051 rules out.
            "gaps": [
                {"at_ms": reaction.at_ms, "duration_ms": reaction.gap_ms}
                for reaction in call.reactions
            ],
        },
    )


def _phonation_share(call: Conversation) -> Measurement | None:
    """F-51. How much of the user's own recording was speech rather than silence.
    Systematically short of 100% (the VAD padding sits in the denominator), so a
    reading against this user's own calls, not an absolute.
    """
    if not call.user_acoustics_complete or not call.user_speech_ms or not _silence_found(call):
        return None
    return Measurement(
        "phonation_share",
        call.user_phonation_ms * 100 / call.user_speech_ms,
        {"speech_ms": call.user_speech_ms, "phonation_ms": call.user_phonation_ms},
    )


def _pauses(call: Conversation) -> Measurement | None:
    """F-51. Average length of a silent stretch inside the user's own speech.

    Only pauses within an utterance count. A hesitation long enough to trip the
    client's VAD ends the Turn instead and is measured as reaction time.
    """
    if not call.pauses or not _silence_found(call):
        return None
    durations = [p.duration_ms for p in call.pauses]
    return Measurement(
        "pauses",
        fmean(durations) / _MS_PER_SECOND,
        {
            "count": len(durations),
            "total_s": sum(durations) / _MS_PER_SECOND,
            "pause_events": [{"start_ms": p.offset_ms, "duration_ms": p.duration_ms} for p in call.pauses],
        },
    )


def _run_length(call: Conversation) -> Measurement | None:
    """F-53. Mean length of runs: phonation over runs, runs = pauses + utterances.
    Hincks (2005): r = 0.72 with liveliness ratings, yet no step -- a correlation
    is not a boundary (ADR 0078). In seconds with a 250 ms pause threshold, so
    **not comparable to a published MLR**; read only against the same speaker.
    """
    # `_silence_found` matters doubly here (ADR 0085): over a noise floor the
    # numerator grows and the denominator shrinks, so the figure comes out
    # several times too high with nothing on screen to look wrong.
    if (not call.user_acoustics_complete or not call.user_turns or
            not _silence_found(call)):
        return None
    return run_length_measurement(
        call.user_phonation_ms, len(call.user_turns), len(call.pauses)
    )


def run_length_measurement(
    phonation_ms: int, utterances: int, pauses: int
) -> Measurement | None:
    """The stored shape: mean run length in seconds, and the terms behind it.
    Shared with `scripts/backfill_run_length.py`; the guards on whether a call
    may be measured stay with the deriver, which has the acoustics.
    """
    runs = utterances + pauses
    if not runs or not phonation_ms:
        return None
    return Measurement(
        RUN_LENGTH_KEY,
        phonation_ms / runs / _MS_PER_SECOND,
        {
            "runs": runs,
            "phonation_ms": phonation_ms,
            # The two terms of the denominator, because a call with many short
            # utterances and one with few interrupted ones reach the same run
            # count by different routes.
            "utterances": utterances,
            "pause_count": pauses,
        },
    )


def _loudness(call: Conversation) -> Measurement | None:
    """F-37. Dynamic range across the whole call as the measure of vocal
    presence, with the curve behind it. A range rather than a level, for the
    reason given on TurnAcoustics.loudness_db (ADR 0047)."""
    audible = sorted(v for v in call.loudness_db if v is not None)
    # Below twenty points the 5% trim rounds to zero, and a single spike decides
    # the "percentile" span alone (24 dB where the trimmed span is 1.5). Withheld
    # below that, as `intonation._band` is.
    if len(audible) < _MIN_LOUDNESS_POINTS or not _silence_found(call):
        return None
    margin = len(audible) // 20  # 5th to 95th percentile, ignoring the extremes
    return Measurement(
        LOUDNESS_KEY,
        audible[-1 - margin] - audible[margin],
        {"curve_db": list(call.loudness_db)},
    )


def _intonation(call: Conversation) -> Measurement | None:
    """F-35. The shape of the user's pitch across the call (see intonation.py).
    The value is the range in semitones -- a ratio, so it describes delivery,
    not the voice's build; the other figures ride in the detail. No norm on the
    range (ADR 0051); the step is read off the PVQ at read time.
    """
    shape = intonation.profile(call.pitch_hz, call.pitch_per_turn)
    if shape.range_st is None:
        return None
    return Measurement(
        "intonation",
        shape.range_st,
        {
            # The curve at the display grid, not at the analysis grid: the
            # statistics above are computed on every 10 ms frame, but three
            # minutes of those is eighteen thousand points and no chart resolves
            # them (intonation.thin).
            "curve_hz": intonation.thin(call.pitch_hz, PITCH_INTERVAL_MS),
            # The grid that thinning actually produced, which is what the
            # drawing's time axis and the seam indices below are in. Never the
            # requested figure -- see `intonation.effective_step_ms`.
            "curve_step_ms": intonation.effective_step_ms(PITCH_INTERVAL_MS),
            # Seams between the user's utterances, as indices into that curve,
            # so a seam is not read as a movement of the voice.
            "turn_breaks": intonation.utterance_breaks(
                call.pitch_per_turn, PITCH_INTERVAL_MS
            ),
            "median_hz": shape.median_hz,
            # The two ends of the range in semitones from that median, which is
            # what the contour draws its band from. Measured rather than assumed
            # symmetric: a voice does not reach as far down as it does up.
            "band_low_st": shape.band_low_st,
            "band_high_st": shape.band_high_st,
            "movement_st_per_s": shape.movement_st_per_s,
            # The PVQ and its window count: the only figure the reading is taken
            # off (Hincks 2005). Stored, unlike the step, since the audio is gone
            # at read time (ADR 0048).
            "pvq": shape.pvq,
            "pvq_windows": shape.pvq_windows,
            # How much voiced speech all of this rests on -- the floor under the
            # five-step reading, and worth showing beside a figure from a short
            # call.
            "voiced_ms": shape.voiced_ms,
            "endings": {
                "falling": shape.endings.falling,
                "rising": shape.endings.rising,
                "level": shape.endings.level,
            },
            "range_first_st": shape.range_first_st,
            "range_last_st": shape.range_last_st,
        },
    )


def _interruptions(call: Conversation) -> Measurement | None:
    """F-51. How often the user cut the Persona off with something still to say,
    as classified in `interruptions.py`. Says how often, not that it was wrong:
    cutting in is often the right move.
    """
    if call.persona_turns == 0:
        return None
    report = classify(call.timeline)
    # The detail is built by the report itself, so the live path and the
    # backfill script cannot drift apart on what travels with the figure.
    return Measurement("interruptions", float(len(report.hard)), report.detail())


# --- The loudness course in words -----------------------------------------

# The wrap-up gets the curve described, not the dB span measured: that span
# reads like a level without being one, and ADR 0051 left it unplaceable.
# frontend/src/components/LoudnessCourse.tsx draws the same curve with the same
# parameters -- keep the two in step.
_SMOOTH_POINTS = 10       # 1 s, at acoustics.py's sample interval
_MIN_STRETCH_POINTS = 20  # 2 s -- below that it is delivery, not a change
# How far outside the call's own spread a stretch has to sit, in multiples of
# it: how unusual it was *for this speaker*, not the "too loud" ADR 0051 rules
# out for want of a norm.
_DEVIATION = 2.0
_LOUDER = "louder"
_QUIETER = "quieter"
_THIRDS = ("in the first third", "in the middle third", "in the final third")


@dataclass(frozen=True)
class _Band:
    """The range the speaker held for most of this call.

    Their own samples are the reference -- ADR 0051 declined to invent an
    external one -- so "louder" only ever means louder than they otherwise were.
    """

    low: float
    high: float

    def direction(self, value: float | None) -> str | None:
        """Which way this sample leaves the band, or None if it stays inside."""
        if value is None:
            return None
        if value > self.high:
            return _LOUDER
        if value < self.low:
            return _QUIETER
        return None

    def distance(self, value: float, direction: str) -> float:
        """How far outside the band this sample sits, in dB."""
        return value - self.high if direction == _LOUDER else self.low - value


def loudness_course(curve: Sequence[float | None]) -> dict | None:
    """F-37's course: the smoothed line, the speaker's own band and at most two
    stretches outside it; None with too little audible speech. Derived on every
    read (ADR 0091) and the only implementation -- the frontend only draws it.
    """
    audible = sorted(value for value in curve if value is not None)
    if len(audible) < _MIN_STRETCH_POINTS:
        return None
    band = _band(audible)
    smoothed = _smooth(curve)
    return {
        "smoothed": smoothed,
        "median": _percentile(audible, 0.5),
        "low": band.low,
        "high": band.high,
        "stretches": [
            {"direction": direction, "peak_index": peak}
            for direction, peak in _find_stretches(smoothed, band)
        ],
    }


def describe_loudness_course(curve: Sequence[float | None]) -> str:
    """F-37's curve as one sentence for the wrap-up prompt, from `loudness_course`.
    Positions are thirds of the user's *own speaking time*, never a timestamp:
    this clock and the transcript's do not agree.
    """
    course = loudness_course(curve)
    if course is None:
        return "Loudness course: too little audible speech to describe."

    stretches = [(s["direction"], s["peak_index"]) for s in course["stretches"]]
    if not stretches:
        return (
            "Loudness course: even -- the user stayed inside their own usual range for "
            "the whole call."
        )

    described = ", ".join(
        f"a {direction} stretch {_THIRDS[min(2, peak * 3 // len(curve))]}"
        for direction, peak in stretches
    )
    return (
        f"Loudness course: {described}. Measured against the range this user held for most "
        "of this call, not against any norm; positions are thirds of their own speaking "
        "time, not of the transcript above."
    )


def _band(audible: list[float]) -> _Band:
    """The call's own middle ground: its median widened by its MAD. Not a
    percentile band, which is blind to shifts covering a fifth to a third of the
    call; a zero MAD falls back to the mean deviation.
    """
    middle = _percentile(audible, 0.5)
    deviations = sorted(abs(value - middle) for value in audible)
    spread = _percentile(deviations, 0.5) or fmean(deviations)
    return _Band(middle - _DEVIATION * spread, middle + _DEVIATION * spread)


def _percentile(sorted_values: list[float], fraction: float) -> float:
    """Linear-interpolated percentile of an already sorted series."""
    at = (len(sorted_values) - 1) * fraction
    below = int(at)
    above = min(below + 1, len(sorted_values) - 1)
    return sorted_values[below] + (sorted_values[above] - sorted_values[below]) * (at - below)


def _smooth(curve: Sequence[float | None]) -> list[float | None]:
    """The curve with the jitter taken out, so a marked stretch is a change in
    the call rather than one stressed syllable. A window more than half silent
    yields no value -- its mean would be the edge of the silence, not a level
    anybody spoke at.
    """
    half = _SMOOTH_POINTS // 2
    smoothed: list[float | None] = []
    for index in range(len(curve)):
        window = [v for v in curve[max(0, index - half):index + half + 1] if v is not None]
        smoothed.append(fmean(window) if len(window) >= half else None)
    return smoothed


def _find_stretches(smoothed: list[float | None], band: _Band) -> list[tuple[str, int]]:
    """At most one stretch per direction -- the one that departed furthest over
    its length -- as (direction, peak index). A steady call yields none.
    """
    marked = [band.direction(value) for value in smoothed]
    best: dict[str, tuple[float, int]] = {}
    index = 0
    while index < len(marked):
        direction = marked[index]
        if direction is None:
            index += 1
            continue
        end = index
        while end < len(marked) and marked[end] == direction:
            end += 1
        if end - index >= _MIN_STRETCH_POINTS:
            _keep_furthest(best, direction, smoothed, range(index, end), band)
        index = end
    return [(direction, best[direction][1]) for direction in (_LOUDER, _QUIETER) if direction in best]


def _keep_furthest(
    best: dict[str, tuple[float, int]],
    direction: str,
    smoothed: list[float | None],
    span: range,
    band: _Band,
) -> None:
    """Keeps this stretch if it departs further than the one already held."""
    deviation = 0.0
    peak = 0.0
    peak_index = span.start
    for index in span:
        value = smoothed[index]
        if value is None:
            continue
        distance = band.distance(value, direction)
        deviation += distance
        if distance > peak:
            peak, peak_index = distance, index
    if direction not in best or deviation > best[direction][0]:
        best[direction] = (deviation, peak_index)


# --- Inventory ------------------------------------------------------------

METRICS: tuple[MetricDef, ...] = (
    # Active. No metric carries a target range: a made-up threshold is a score
    # in disguise (ADR 0004/0051). `aspect` picks the screen's half (ADR 0082);
    # talk share is `what`: it describes the exchange, not the delivery.
    MetricDef("talk_share", "Redeanteil", "%", ASPECT_WHAT, "F-24", True, _talk_share),
    MetricDef("questions", "Fragen an den Gesprächspartner", "Anzahl", ASPECT_WHAT, "F-41",
              True, _questions),
    MetricDef("pace", "Sprechtempo", "Wörter/min", ASPECT_HOW, "F-36", True, _pace),
    MetricDef("word_count", "Gesprochene Wörter", "Wörter", ASPECT_WHAT, "F-08", True,
              _word_count),
    MetricDef("fillers", "Füllwörter", "Anzahl", ASPECT_WHAT, "F-51", True, _fillers),
    # Three parts checked, hence the unit; a fourth needs it changed with it.
    MetricDef("opening", "Gesprächseinstieg", "von 3", ASPECT_WHAT, "F-63", True, _opening),
    # Its counterpart at the other end of the call (ADR 0089), and the same
    # unit for the same reason.
    MetricDef(CLOSING_KEY, "Gesprächsabschluss", "von 3", ASPECT_WHAT, "F-65", True, _closing),
    MetricDef("repetitions", "Wiederholungen", "Anzahl", ASPECT_WHAT, "F-08", True,
              _repetitions),
    MetricDef("hesitations", "Verzögerungslaute", "Anzahl", ASPECT_HOW, "F-51", True,
              _hesitations),
    MetricDef("reaction_time", "Reaktionszeit", "s", ASPECT_HOW, "F-53", True, _reaction_time),
    MetricDef("pauses", "Sprechpausen", "s", ASPECT_HOW, "F-51", True, _pauses),
    MetricDef("phonation_share", "Redefluss", "%", ASPECT_HOW, "F-51", True, _phonation_share),
    MetricDef(RUN_LENGTH_KEY, "Sprechlänge am Stück", "s", ASPECT_HOW, "F-53", True,
              _run_length),
    MetricDef(LOUDNESS_KEY, "Lautstärke", "dB", ASPECT_HOW, "F-37", True, _loudness),
    # F-35, a MUST that had no measurement until the pitch curve existed. The
    # unit is semitones so the figure describes delivery rather than the voice
    # it was spoken with -- see `_intonation`.
    MetricDef("intonation", "Sprachmelodie", "Halbtöne", ASPECT_HOW, "F-35", True, _intonation),
    # F-51's third element beside pauses (ADR 0035). A count, not a rate: per
    # Persona turn it put every single interruption on the top step.
    MetricDef("interruptions", "Unterbrechungen", "Anzahl", ASPECT_HOW, "F-51", True,
              _interruptions),
    # SHOULD / COULD -- seeded so the vocabulary is complete, but inactive and
    # without a derivation.
    MetricDef("concreteness", "Sprachliche Konkretheit", None, ASPECT_WHAT, "F-40", False),
    # F-42 ships, but as prose and not as a figure: what it describes is a
    # change of register across the call's three phases, which no single value
    # carries and which would need a norm nobody measured to score. It is the
    # `phase_language` paragraph of the wrap-up (backend/feedback/generator.py).
    # The row stays inactive and seeded so the vocabulary keeps its entry.
    MetricDef("phase_appropriate_language", "Phasengerechte Sprache", None, ASPECT_HOW,
              "F-42", False),
    MetricDef("congruence", "Kongruenz von Inhalt und Stimme", None, ASPECT_HOW, "F-39", False),
)


# Below this share of silent frames the recording has no silence the threshold
# could find: a noise floor, not a speaker who never paused. Stored calls run at
# 37 to 67 %; one recorded over background noise came out at 0.6 %.
_MIN_SILENT_SHARE = 0.10


def _silence_found(call: Conversation) -> bool:
    """Whether the recording separated speech from silence at all.

    Pauses, phonation and the loudness span rest on that split; without it they
    would report the noise as speech. Absent beats wrong (ADR 0051).
    """
    if not call.loudness_db:
        return True
    silent = sum(1 for value in call.loudness_db if value is None)
    return silent / len(call.loudness_db) >= _MIN_SILENT_SHARE


def _pack(call: Conversation) -> LanguagePack | None:
    """The call's language pack, or None. `.get`, not `get_pack`: a missing
    pack costs one detail, raising would cost every statistic."""
    return LANGUAGE_PACKS.get(call.language_id or "")


def _count_words(text: str) -> int:
    return len(_WORD_RE.findall(text))
