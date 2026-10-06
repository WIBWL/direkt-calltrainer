"""The metric inventory and how each metric is derived from a whole call (ADR 0051)."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from statistics import fmean

from shared.db.models import ASPECT_HOW, ASPECT_WHAT
from shared.feedback import hesitations, intonation
from shared.feedback.calls import Conversation, Reaction
from shared.feedback.interruptions import classify
from shared.language_packs import LANGUAGE_PACKS, LanguagePack

_MS_PER_MINUTE = 60_000
_MS_PER_SECOND = 1000

RUN_LENGTH_KEY = "run_length"

# Letter runs only, so punctuation and digits don't count as words.
_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)
_SENTENCE_END_RE = re.compile(r"[.!?]+")
_SENTENCE_SPLIT_RE = re.compile(r"[.!]+")
LOUDNESS_KEY = "loudness"
# Below this the 5th-95th percentile trims nothing.
_MIN_LOUDNESS_POINTS = 20

# Not 100 ms like loudness: that aliases the syllable rate into a sawtooth.
PITCH_INTERVAL_MS = 50


@dataclass(frozen=True)
class Measurement:
    key: str
    value: float
    detail: dict | None = None


Deriver = Callable[[Conversation], "Measurement | None"]


@dataclass(frozen=True)
class MetricDef:
    key: str
    name: str
    unit: str | None
    aspect: str  # display grouping only, never in the prompt
    feature_id: str
    active: bool
    derive: Deriver | None = None


def measure(call: Conversation) -> list[Measurement]:
    """A metric that cannot be computed is absent, never a stand-in zero."""
    derived = (metric.derive(call) for metric in METRICS if metric.derive)
    return [m for m in derived if m is not None]


def _talk_share(call: Conversation) -> Measurement | None:
    """F-24. Speaking time, not wall-clock; pauses in, VAD padding out (ADR 0114)."""
    if not call.user_acoustics_complete or not _silence_found(call):
        return None
    # Words without measured time mean the measurement failed (ADR 0048).
    if call.user_text and not call.user_voiced_ms:
        return None
    return talk_share_measurement(call.user_voiced_ms, call.persona_speech_ms)


def talk_share_measurement(user_ms: int, persona_ms: int) -> Measurement | None:
    spoken = user_ms + persona_ms
    if not spoken:
        return None
    return Measurement(
        "talk_share", user_ms * 100 / spoken, {"user_ms": user_ms, "persona_ms": persona_ms}
    )


def _questions(call: Conversation) -> Measurement | None:
    """F-41. Counted from question marks; a keyword list would miss German inversions."""
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
    """F-51. Lexical fillers only: Whisper drops "äh"."""
    pack = _pack(call)
    words = _count_words(call.user_text)
    if not pack or not words:
        return None
    found = Counter(" ".join(hit.lower().split()) for hit in pack.filler_re.findall(call.user_text))
    count = sum(found.values())
    return Measurement(
        "fillers",
        float(count),
        {"per_100_words": count * 100 / words, "words": dict(found.most_common())},
    )


def _repetitions(call: Conversation) -> Measurement | None:
    """F-08. Word-for-word repeats; overlapping matches merge."""
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


_REPEAT_WORDS = 4


def _repeated_passages(words: list[str]) -> list[str]:
    folded = [word.lower() for word in words]
    first_seen: dict[tuple[str, ...], int] = {}
    covered = [False] * len(words)
    for index in range(len(words) - _REPEAT_WORDS + 1):
        gram = tuple(folded[index:index + _REPEAT_WORDS])
        first = first_seen.setdefault(gram, index)
        # Non-overlapping only: "ja ja ja ja ja" is stammering, not repetition.
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
    """F-51. Estimated from the pitch contour; absent if any Turn's acoustics failed."""
    if not call.user_acoustics_complete or not call.pitch_per_turn:
        return None
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


_MIN_OPENING_WORDS = 4
_MIN_REST_WORDS = 15


def _opening(call: Conversation) -> Measurement | None:
    """F-63. Greeting, name, offer (or concern, when the user rang), plus relative tempo."""
    pack = _pack(call)
    if not pack or not call.user_turns:
        return None
    found = opening_parts(call.user_turns[0][0], pack, reverse=call.reverse)
    return Measurement(
        "opening", float(sum(found.values())), found | {"pace_ratio": _opening_pace(call)}
    )


def opening_parts(first_text: str, pack: LanguagePack, *, reverse: bool) -> dict[str, bool]:
    return {
        "greeting": bool(pack.greeting_re.search(first_text)),
        "name": bool(pack.self_intro_re.search(first_text)),
        ("concern" if reverse else "offer"): bool(
            (pack.concern_re if reverse else pack.offer_re).search(first_text)
        ),
    }


def _opening_pace(call: Conversation) -> float | None:
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

# The recap usually comes a turn before the goodbye (ADR 0089).
CLOSING_WINDOW = 2

# Matches `MIN_USER_TURNS` in FeedbackReport.tsx.
MIN_CLOSING_TURNS = 3


def closing_parts(user_texts: Sequence[str], pack: LanguagePack) -> dict[str, bool] | None:
    if len(user_texts) < MIN_CLOSING_TURNS:
        return None
    window = " ".join(user_texts[-CLOSING_WINDOW:])
    return {
        "recap": bool(pack.recap_re.search(window)),
        "agreement": bool(pack.agreement_re.search(window)),
        "farewell": bool(pack.sign_off_re.search(window)),
    }


def closing_measurement(parts: dict[str, bool]) -> Measurement:
    return Measurement(
        CLOSING_KEY, float(sum(parts.values())), parts | {"turns_read": CLOSING_WINDOW}
    )


def _closing(call: Conversation) -> Measurement | None:
    """ADR 0089. Recap, next step and goodbye, whoever rang."""
    pack = _pack(call)
    if not pack:
        return None
    parts = closing_parts([text for text, _ in call.user_turns], pack)
    return closing_measurement(parts) if parts is not None else None


def _open_questions(text: str, pack: LanguagePack) -> int:
    return sum(
        1 for segment in text.split("?")[:-1]
        if pack.open_question_re.match(_SENTENCE_SPLIT_RE.split(segment)[-1].strip())
    )


def _pace(call: Conversation) -> Measurement | None:
    """F-36. Words per minute of phonation; never relative to the Persona (ADR 0051)."""
    words = _count_words(call.user_text)
    measurable = call.user_acoustics_complete and call.user_phonation_ms and _silence_found(call)
    if not words or not measurable:
        return None
    return Measurement(
        "pace",
        words * _MS_PER_MINUTE / call.user_phonation_ms,
        {"words": words, "phonation_ms": call.user_phonation_ms},
    )


def _word_count(call: Conversation) -> Measurement | None:
    """F-08."""
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
    """F-53. Persona silent to user's first sound; model latency is outside it."""
    return reaction_time_measurement(call.reactions)


def reaction_time_measurement(reactions: Sequence[Reaction]) -> Measurement | None:
    if not reactions:
        return None
    gaps = [reaction.gap_ms for reaction in reactions]
    return Measurement(
        "reaction_time",
        fmean(gaps) / _MS_PER_SECOND,
        {
            "longest_s": max(gaps) / _MS_PER_SECOND,
            "count": len(gaps),
            "gaps": [
                {"at_ms": reaction.at_ms, "duration_ms": reaction.gap_ms}
                for reaction in reactions
            ],
        },
    )


def _phonation_share(call: Conversation) -> Measurement | None:
    """F-51. Phonation over first-sound-to-last span, not the padded recording (ADR 0114)."""
    if not call.user_acoustics_complete or not call.user_phonation_ms or not _silence_found(call):
        return None
    return phonation_share_measurement(call.user_phonation_ms, call.user_voiced_ms)


def phonation_share_measurement(phonation_ms: int, voiced_ms: int) -> Measurement | None:
    if not voiced_ms:
        return None
    return Measurement(
        "phonation_share",
        phonation_ms * 100 / voiced_ms,
        {"voiced_ms": voiced_ms, "phonation_ms": phonation_ms},
    )


def _pauses(call: Conversation) -> Measurement | None:
    """F-51. Pauses within an utterance; a longer one ends the Turn instead."""
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
    """F-53. Mean run length. 250 ms pause threshold: not comparable to a published MLR."""
    if (not call.user_acoustics_complete or not call.user_turns or
            not _silence_found(call)):
        return None
    return run_length_measurement(
        call.user_phonation_ms, len(call.user_turns), len(call.pauses)
    )


def run_length_measurement(
    phonation_ms: int, utterances: int, pauses: int
) -> Measurement | None:
    runs = utterances + pauses
    if not runs or not phonation_ms:
        return None
    return Measurement(
        RUN_LENGTH_KEY,
        phonation_ms / runs / _MS_PER_SECOND,
        {
            "runs": runs,
            "phonation_ms": phonation_ms,
            "utterances": utterances,
            "pause_count": pauses,
        },
    )


def _loudness(call: Conversation) -> Measurement | None:
    """F-37. Dynamic range, not level (ADR 0047)."""
    audible = sorted(v for v in call.loudness_db if v is not None)
    if len(audible) < _MIN_LOUDNESS_POINTS or not _silence_found(call):
        return None
    margin = len(audible) // 20  # 5th to 95th percentile
    return Measurement(
        LOUDNESS_KEY,
        audible[-1 - margin] - audible[margin],
        {"curve_db": list(call.loudness_db)},
    )


def _intonation(call: Conversation) -> Measurement | None:
    """F-35. Range in semitones, so it describes delivery, not the voice."""
    shape = intonation.profile(call.pitch_hz, call.pitch_per_turn)
    if shape.range_st is None:
        return None
    return Measurement(
        "intonation",
        shape.range_st,
        {
            "curve_hz": intonation.thin(call.pitch_hz, PITCH_INTERVAL_MS),
            # The grid thinning actually produced, not the requested one.
            "curve_step_ms": intonation.effective_step_ms(PITCH_INTERVAL_MS),
            "turn_breaks": intonation.utterance_breaks(
                call.pitch_per_turn, PITCH_INTERVAL_MS
            ),
            "median_hz": shape.median_hz,
            "band_low_st": shape.band_low_st,
            "band_high_st": shape.band_high_st,
            "movement_st_per_s": shape.movement_st_per_s,
            "pvq": shape.pvq,
            "pvq_windows": shape.pvq_windows,
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
    """F-51. Hard interruptions of the Persona."""
    if call.persona_turns == 0:
        return None
    report = classify(call.timeline)
    return Measurement("interruptions", float(len(report.hard)), report.detail())


# Keep in step with frontend/src/components/LoudnessCourse.tsx.
_SMOOTH_POINTS = 10       # 1 s
_MIN_STRETCH_POINTS = 20  # 2 s
_DEVIATION = 2.0  # multiples of the speaker's own spread; no external norm (ADR 0051)
_LOUDER = "louder"
_QUIETER = "quieter"
_THIRDS = ("in the first third", "in the middle third", "in the final third")


@dataclass(frozen=True)
class _Band:
    low: float
    high: float

    def direction(self, value: float | None) -> str | None:
        if value is None:
            return None
        if value > self.high:
            return _LOUDER
        if value < self.low:
            return _QUIETER
        return None

    def distance(self, value: float, direction: str) -> float:
        return value - self.high if direction == _LOUDER else self.low - value


def loudness_course(curve: Sequence[float | None]) -> dict | None:
    """F-37's course, derived on every read (ADR 0091); the frontend only draws it."""
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
    """Positions are thirds of the user's speaking time; this clock isn't the transcript's."""
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
    """Median ± MAD; a percentile band would miss shifts covering a third of the call."""
    middle = _percentile(audible, 0.5)
    deviations = sorted(abs(value - middle) for value in audible)
    spread = _percentile(deviations, 0.5) or fmean(deviations)
    return _Band(middle - _DEVIATION * spread, middle + _DEVIATION * spread)


def _percentile(sorted_values: list[float], fraction: float) -> float:
    at = (len(sorted_values) - 1) * fraction
    below = int(at)
    above = min(below + 1, len(sorted_values) - 1)
    return sorted_values[below] + (sorted_values[above] - sorted_values[below]) * (at - below)


def _smooth(curve: Sequence[float | None]) -> list[float | None]:
    # A window more than half silent yields no value.
    half = _SMOOTH_POINTS // 2
    smoothed: list[float | None] = []
    for index in range(len(curve)):
        window = [v for v in curve[max(0, index - half):index + half + 1] if v is not None]
        smoothed.append(fmean(window) if len(window) >= half else None)
    return smoothed


def _find_stretches(smoothed: list[float | None], band: _Band) -> list[tuple[str, int]]:
    """At most one stretch per direction, as (direction, peak index)."""
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


METRICS: tuple[MetricDef, ...] = (
    # No metric carries a target range (ADR 0004/0051).
    MetricDef("talk_share", "Redeanteil", "%", ASPECT_WHAT, "F-24", True, _talk_share),
    MetricDef("questions", "Fragen an den Gesprächspartner", "Anzahl", ASPECT_WHAT, "F-41",
              True, _questions),
    MetricDef("pace", "Sprechtempo", "Wörter/min", ASPECT_HOW, "F-36", True, _pace),
    MetricDef("word_count", "Gesprochene Wörter", "Wörter", ASPECT_WHAT, "F-08", True,
              _word_count),
    MetricDef("fillers", "Füllwörter", "Anzahl", ASPECT_WHAT, "F-51", True, _fillers),
    MetricDef("opening", "Gesprächseinstieg", "von 3", ASPECT_WHAT, "F-63", True, _opening),
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
    MetricDef("intonation", "Sprachmelodie", "Halbtöne", ASPECT_HOW, "F-35", True, _intonation),
    # A count, not a rate: per Persona turn put every interruption on the top step.
    MetricDef("interruptions", "Unterbrechungen", "Anzahl", ASPECT_HOW, "F-51", True,
              _interruptions),
    # Inactive: seeded so the vocabulary is complete.
    MetricDef("concreteness", "Sprachliche Konkretheit", None, ASPECT_WHAT, "F-40", False),
    # Ships as the wrap-up's `phase_language` prose, not a figure.
    MetricDef("phase_appropriate_language", "Phasengerechte Sprache", None, ASPECT_HOW,
              "F-42", False),
    MetricDef("congruence", "Kongruenz von Inhalt und Stimme", None, ASPECT_HOW, "F-39", False),
)


# Below this the recording is a noise floor, not a speaker who never paused.
_MIN_SILENT_SHARE = 0.10


def _silence_found(call: Conversation) -> bool:
    """Whether the recording separated speech from silence at all (ADR 0085)."""
    if not call.loudness_db:
        return True
    silent = sum(1 for value in call.loudness_db if value is None)
    return silent / len(call.loudness_db) >= _MIN_SILENT_SHARE


def _pack(call: Conversation) -> LanguagePack | None:
    # `.get`: a missing pack costs one detail; raising would cost every statistic.
    return LANGUAGE_PACKS.get(call.language_id or "")


def _count_words(text: str) -> int:
    return len(_WORD_RE.findall(text))
