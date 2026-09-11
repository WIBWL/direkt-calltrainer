"""The MetricType inventory and the derivation of a Session's Measurement rows.

Single source of truth for the metrics: one entry per metric holds both its
reference data (what backend/db/provision.py writes into the metric_type table)
and how its value is derived. Adding a metric is one entry here, not a change
spread over a seed and an analysis path.

Every metric describes the whole call, not one utterance (ADR 0051): the
inventory follows F-53's list of Kennzahlen -- Redeanteil, Fragen, Sprechtempo,
Wortanzahl, Reaktionszeit, Pausen -- plus the loudness curve of F-37. The Prio
column of docs/features.md drives `active`; an inactive metric carries no
`derive` and produces nothing, so the MVP's scope stays unambiguous.

This module knows nothing about Praat. It turns the numbers acoustics.py
measured into the domain's vocabulary, and it is where every judgment about
what those numbers mean would go.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from statistics import fmean

from backend.db.models import ASPECT_HOW, ASPECT_WHAT
from backend.feedback import hesitations, intonation
from backend.feedback.acoustics import Pause
from backend.feedback.interruptions import Segment, classify
from backend.session.language_packs import LANGUAGE_PACKS, LanguagePack

_MS_PER_MINUTE = 60_000
_MS_PER_SECOND = 1000

# The metric key `_run_length` feeds, named here so the API and the tests agree
# on the string rather than each spelling it out.
RUN_LENGTH_KEY = "run_length"

# The text behind that Kennzahl's "i", kept beside the derivation it explains.
# Plain German, no dashes: it is read by somebody who has just finished a call.
RUN_LENGTH_EXPLANATION = (
    "Gemessen wird, wie lange Sie am Stück sprechen, bevor Sie absetzen. Ihre "
    "reine Sprechzeit geteilt durch die Anzahl Ihrer Sprechabschnitte. Als "
    "Abschnitt zählt alles zwischen zwei Pausen ab einer Viertelsekunde "
    "innerhalb einer Äußerung; eine längere Unterbrechung beendet die Äußerung "
    "und taucht stattdessen in der Reaktionszeit auf. "
    "Diese Zahl beschreibt als einzige hier das Sprechen selbst und nicht die "
    "Stille dazwischen. Zwei Menschen können denselben Redefluss und dieselbe "
    "mittlere Pausenlänge haben und trotzdem sehr verschieden klingen: der eine "
    "spricht in Zwei-Wort-Häppchen, der andere in ganzen Sätzen. Genau das "
    "steht hier. "
    "Eine Einordnung gibt es bewusst nicht. In der Forschung hängt dieses Maß "
    "eng damit zusammen, wie lebendig Zuhörer jemanden finden, enger sogar als "
    "die Tonhöhenschwankung. Ein Zusammenhang ist aber kein Grenzwert, und es "
    "ist nirgends belegt, ab wann ein Abschnitt zu kurz ist. Wie lang er sein "
    "sollte, hängt außerdem vom Gespräch ab: wer zuhört und kurz bestätigt, "
    "spricht zu Recht in kurzen Abschnitten. "
    "Vergleichen Sie die Zahl deshalb nur mit Ihren eigenen anderen Gesprächen. "
    "Weil wir schon ab einer Viertelsekunde trennen, fallen die Abschnitte "
    "kürzer aus als in Veröffentlichungen zu diesem Maß, die meist später "
    "trennen."
)
# Words, for rate denominators: letter runs, so punctuation and the digits STT
# writes for numbers don't inflate the count.
_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)
_SENTENCE_END_RE = re.compile(r"[.!?]+")
# The same, minus the question mark: a segment a question mark already ended.
_SENTENCE_SPLIT_RE = re.compile(r"[.!]+")
# The one metric the wrap-up reads as a course rather than as a figure, so
# generator.py has to be able to pick it out of the inventory by name.
LOUDNESS_KEY = "loudness"
# The grid the stored curves are drawn at, matching acoustics.py's loudness
# sampling so the two can be read side by side.
LOUDNESS_INTERVAL_MS = 100

# The pitch curve is stored at half of that, and does not share the grid.
#
# Measured, on a synthetic contour with speech's own syllable rate: at 100 ms
# the drawing turns into a sawtooth, because roughly 4 to 5 syllables a second
# sampled ten times a second is barely above the point where the movement folds
# back on itself. The picture stops being a contour and becomes noise, which is
# the same aliasing that ADR 0051's audit found in the *statistics* and fixed
# there by measuring at 10 ms -- only the drawing was left behind.
#
# 50 ms is a whole number of analysis frames (so `thin` produces exactly this
# grid, see `effective_step_ms`), samples the syllable rate about ten times
# over, and doubles the stored curve: about 2.5 KB for twenty seconds of
# speaking time, 25 KB for a long call, all of it in `detail_json`, which the
# listing route does not serve.
PITCH_INTERVAL_MS = 50


@dataclass(frozen=True)
class Conversation:  # pylint: disable=too-many-instance-attributes  # a record of measured facts, one field per fact
    """One finished call, reduced to the facts the statistics are derived from.

    Assembled by backend/session/models.py, which owns the Turn timeline and
    keeps the machine's latency out of both speakers' windows (ADR 0051).
    """

    user_text: str = ""
    # For the metrics that read words rather than milliseconds. None means
    # they report what they can without a vocabulary.
    language_id: str | None = None
    # A reverse (ADR 0070): the user rang. Decides the opening's third part.
    reverse: bool = False
    # How long the user's audio ran, and how much of that was speech rather
    # than silence. Only the first is comparable with `persona_speech_ms`.
    user_speech_ms: int = 0
    user_phonation_ms: int = 0
    # False when a Turn's measurement failed, leaving both figures short by an
    # unknown amount (ADR 0048).
    user_acoustics_complete: bool = True
    # Only ever a denominator, for the user's share of the speaking time.
    persona_speech_ms: int = 0
    # One entry per exchange: how long the user took to start replying,
    # counted from the moment the Persona stopped speaking.
    reactions_ms: tuple[int, ...] = ()
    # Silent stretches inside the user's own speech, on the Session's timeline.
    pauses: tuple[Pause, ...] = ()
    # The user's loudness across the whole call, at acoustics.py's fixed rate.
    loudness_db: tuple[float | None, ...] = ()
    # The user's fundamental frequency at acoustics.py's 10 ms grid, None where
    # the frame was unvoiced (F-35). Finer than the loudness curve on purpose:
    # a 100 ms grid aliases the movement that intonation lives in.
    pitch_hz: tuple[float | None, ...] = ()
    # The same frames grouped by utterance, which the terminal contours need:
    # "how did this sentence end" has no answer on a contour with the sentence
    # boundaries taken out.
    pitch_per_turn: tuple[tuple[float | None, ...], ...] = ()
    # The user's turns in order, as (text, phonation ms): the opening is the
    # first of them, and its tempo is read against the rest. How many there are
    # is also F-53's denominator -- a run of speech is bounded by a pause inside
    # an utterance or by the utterance itself, so the runs of a call are its
    # pauses plus these.
    user_turns: tuple[tuple[str, int], ...] = ()
    # How many Persona replies there were, which is what the interruption rate
    # divides by.
    persona_turns: int = 0
    # The bare segments the overlap classification of F-51 runs on. Empty for a
    # call whose sides were never measured, in which case no overlap can be
    # established either way.
    timeline: tuple[Segment, ...] = ()


@dataclass(frozen=True)
class Measurement:
    """One Measurement to be written against a Session: a value plus ADR 0029's detail."""

    key: str
    value: float
    detail: dict | None = None


# A deriver sees the whole call and returns its metric's Messung -- or None
# when the call gave it nothing to measure.
Deriver = Callable[[Conversation], "Measurement | None"]


@dataclass(frozen=True)
class MetricDef:
    """One row of the metric_type reference table, plus how to compute and judge it."""

    key: str
    name: str
    unit: str | None
    # ASPECT_HOW or ASPECT_WHAT: which half of the Kennzahlen grid this one
    # sits in. A display grouping -- it never reaches the wrap-up prompt.
    aspect: str
    feature_id: str
    active: bool
    derive: Deriver | None = None


def measure(call: Conversation) -> list[Measurement]:
    """Derive every active metric for one finished Session.

    A metric that cannot be computed for this call is absent from the result
    rather than present with a stand-in value: a missing Measurement row is
    honest, a zero would be read as a measurement.
    """
    derived = (metric.derive(call) for metric in METRICS if metric.derive)
    return [m for m in derived if m is not None]


# --- Derivations ----------------------------------------------------------


def _talk_share(call: Conversation) -> Measurement | None:
    """F-24. The user's share of the time either side actually spoke -- speaking
    time, not wall-clock, so the model's own latency dilutes neither share.

    Audio duration on both sides: the Persona's figure is the length of the
    audio synthesized for it, so the user's has to be the length of their
    recording. Phonation as the numerator would strip the user's silences and
    not the Persona's, reporting that difference as a smaller share.
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
    """F-41. Questions the user asked -- the observable trace of active
    listening, and the one thing a caller notices the absence of.

    Counted from the transcript's own punctuation: STT punctuates German
    reliably enough, and a keyword list would miss the inversions
    ("Koennen Sie mir sagen...") that carry most German questions.

    The detail splits them into open and closed. Both halves are read off the
    same question marks, so they always add up to the count.
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
    found = [hold for turn in call.pitch_per_turn for hold in hesitations.holds(turn)]
    return Measurement(
        "hesitations",
        float(len(found)),
        {"total_ms": sum(hold.duration_ms for hold in found)},
    )


# Below these the opening's tempo is not compared: a handful of words gives a
# rate, not a tempo.
_MIN_OPENING_WORDS = 4
_MIN_REST_WORDS = 15


def _opening(call: Conversation) -> Measurement | None:
    """F-63. Whether the user's first turn greets, names them and offers help --
    or, when they rang, states the concern -- plus its tempo against the rest.

    Reads the frames these are said in, so a bare name ("Schmidt, guten Tag")
    goes unrecognised: the screen says "nicht erkannt", never "fehlt".
    """
    pack = _pack(call)
    if not pack or not call.user_turns:
        return None
    first = call.user_turns[0][0]
    found = {
        "greeting": bool(pack.greeting_re.search(first)),
        "name": bool(pack.self_intro_re.search(first)),
        # Stored under its own key, so the screen can name the part checked.
        ("concern" if call.reverse else "offer"): bool(
            (pack.concern_re if call.reverse else pack.offer_re).search(first)
        ),
    }
    return Measurement(
        "opening", float(sum(found.values())), found | {"pace_ratio": _opening_pace(call)}
    )


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

# The closing is read in the user's last this-many turns (ADR 0089). Two, not
# one: a recap or the agreed next step usually comes a turn before the goodbye,
# with the Persona's answer in between, and the last turn alone is often only
# "Danke, auf Wiederhören". Not three: at the six to nine turns these calls run
# to, three is a third of the call, and a "bis Freitag" from its middle would
# pass for an agreement.
CLOSING_WINDOW = 2

# Below this many user turns there is no closing to speak of, and the window
# would reach back into the opening. The same floor below which the post-call
# screen offers neither a follow-up nor a reverse (`MIN_USER_TURNS` in
# FeedbackView.tsx): a call hung up after a sentence or two has no end of its own.
MIN_CLOSING_TURNS = 3


def closing_parts(user_texts: Sequence[str], pack: LanguagePack) -> dict[str, bool] | None:
    """The three parts of a closing, found in the last `CLOSING_WINDOW` of
    `user_texts` -- or None when there are too few turns to have a closing.

    A function of its own, not only the deriver's body, because it is what
    `scripts/backfill_closing.py` runs over stored transcripts: the parts come
    from words alone, so unlike the acoustic metrics they can reach calls
    recorded before this existed (ADR 0048 does not bite).
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
    """ADR 0089. Whether the user's last two turns sum up what was settled, name
    a concrete next step and say goodbye.

    The same parts whoever rang, unlike the opening: ending a call well asks the
    same of both sides. Reads the phrases these are said in, so a recap worded
    some other way goes unrecognised -- the screen says "nicht erkannt", never
    "fehlt", exactly as for the opening.
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
    """F-36. Words per minute of speaking time, since that is the unit the user
    thinks in. The gaps between utterances are excluded, so this says how fast
    they talk rather than how much of the call they filled.

    F-36 also asks for the rate "relativ zum Gesprächspartner". That partner is
    a synthesized voice reading at whatever rate the TTS model was configured
    for, so the comparison would measure a setting, not the user; it is left
    out until the partner is a person.

    The denominator is phonation: Praat's silence segmentation (the same pass
    that yields F-51's pauses) drops the silences inside the utterance along
    with the pre-speech and redemption frames the client's VAD pads each
    recording with, leaving only time the user was actually speaking in.
    """
    words = _count_words(call.user_text)
    measurable = call.user_acoustics_complete and call.user_phonation_ms and _silence_found(call)
    if not words or not measurable:
        return None
    return Measurement("pace", words * _MS_PER_MINUTE / call.user_phonation_ms)


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
    if not call.reactions_ms:
        return None
    return Measurement(
        "reaction_time",
        fmean(call.reactions_ms) / _MS_PER_SECOND,
        {"longest_s": max(call.reactions_ms) / _MS_PER_SECOND, "count": len(call.reactions_ms)},
    )


def _phonation_share(call: Conversation) -> Measurement | None:
    """F-51. How much of the user's own recording was speech rather than
    silence -- the companion to `_pauses`, which knows only an average length.

    Systematically short of 100%: the client's VAD pads every recording, and
    that padding sits in the denominator. A reading against this user's own
    calls, not an absolute.
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
    """How long the user speaks before they break off (mean length of runs).

    A run is a stretch of speech bounded by silence. Inside one utterance, a
    pause ends a run and starts the next, so an utterance holding `p` pauses
    holds `p + 1` runs, and the whole call holds its pauses plus its
    utterances. Divide the speaking time by that and you have the average
    length of a stretch spoken without breaking off.

    This is the one figure here about the *speech*, not about the silence.
    `_pauses` reports how long a break lasts and `_phonation_share` how much of
    the recording was speech at all, and a speaker can score the same on both
    while sounding entirely different: two-word bursts and whole sentences run
    at the same phonation share if the pauses between them match.

    Why this one and not another paraverbal figure: it is the only measure in
    this module that has been checked against what listeners actually hear.
    Hincks (2005) found mean length of runs correlating with liveliness ratings
    at r = 0.72 for female speakers, ahead of the pitch variation quotient's
    0.64 -- which is to say the figure F-35's whole reading rests on was beaten
    by this one on the same data.

    No step and no colour all the same. A correlation is not a boundary, and
    nothing published says where a short run stops being conversational, so
    ADR 0078's first condition is not met and this stays a bare figure
    (ADR 0004/0051).

    Two things bound what it can mean here, and the note beside it says both.
    Runs are separated by pauses of at least 250 ms inside an utterance
    (`acoustics._MIN_PAUSE_S`); a hesitation long enough to trip the 500 ms VAD
    ends the utterance instead and is counted as reaction time. And the figure
    is in seconds rather than in syllables, which is what the literature counts,
    because nothing here counts syllables and Whisper's words are a poor
    substitute for them.

    A third thing follows from the first and is worth stating before somebody
    compares this against a published figure: **the number is not comparable to
    one.** 250 ms is Praat's silence threshold, inherited because that is what
    already segmented this audio, and it is at the short end of what fluency
    research uses. A shorter threshold finds more pauses, so it produces more
    and shorter runs; the first real call measured here came out at 1.2 s over
    27 runs, well under the figures the literature reports for the same measure
    at a longer threshold. That costs nothing as long as the figure is only ever
    read against this speaker's own other calls, which is all ADR 0051 allows
    anyway, and it is exactly why no step was put on it.
    """
    if not call.user_acoustics_complete or not call.user_turns:
        return None
    runs = len(call.user_turns) + len(call.pauses)
    if not call.user_phonation_ms:
        return None
    return Measurement(
        RUN_LENGTH_KEY,
        call.user_phonation_ms / runs / _MS_PER_SECOND,
        {
            "runs": runs,
            "phonation_ms": call.user_phonation_ms,
            # The two terms of the denominator, because a call with many short
            # utterances and one with few interrupted ones reach the same run
            # count by different routes.
            "utterances": len(call.user_turns),
            "pause_count": len(call.pauses),
        },
    )


def _loudness(call: Conversation) -> Measurement | None:
    """F-37. Dynamic range across the whole call as the measure of vocal
    presence, with the curve behind it. A range rather than a level, for the
    reason given on TurnAcoustics.loudness_db (ADR 0047)."""
    audible = sorted(v for v in call.loudness_db if v is not None)
    if len(audible) < 3 or not _silence_found(call):
        return None
    margin = len(audible) // 20  # 5th to 95th percentile, ignoring the extremes
    return Measurement(
        LOUDNESS_KEY,
        audible[-1 - margin] - audible[margin],
        {"curve_db": list(call.loudness_db)},
    )


def _intonation(call: Conversation) -> Measurement | None:
    """F-35. The shape of the user's pitch across the call.

    Four factors rather than one figure, because one figure could not tell a
    lively speaker from one who said a single sentence brightly, nor a speaker
    who closes their sentences from one who ends every one of them on a rise.
    `backend/feedback/intonation.py` derives them and says why each was chosen.

    The value stays the range in semitones, so the Kennzahl keeps one number the
    way every other one does; the factors ride in the detail.

    Semitones and not Hertz, and this is the point of the unit. A range of 40 Hz
    is a lot for a low voice and little for a high one, so a figure in Hertz
    would report the speaker's build as though it were their delivery. A
    semitone is a ratio, so the same expressive range yields the same number for
    any voice -- which is also how phonetics states pitch variability.

    No norm is attached, and none is implied. F-35 speaks of making monotony
    visible, but where a lively range ends and a monotone one begins is exactly
    the threshold ADR 0051 declined to invent. The figures are reported; what
    they mean is for the user and for the wrap-up's prose.
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
            # Where one of the user's utterances ends and the next begins, as
            # indices into that curve. The curve is speaking time, not call
            # time: the Persona's turns are not in it at all, so without these
            # a seam between two utterances would read as a movement of the
            # voice.
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
            # The pitch variation quotient and the number of ten-second windows
            # it was averaged over. The reading on this Kennzahl is taken off
            # this figure and off nothing else -- it is the only one of the five
            # with a published boundary behind it (Hincks 2005). Stored rather
            # than derived at read time, unlike the step itself: it is a
            # measurement, and the audio it needs is gone by then (ADR 0048).
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
    """F-51. How often the user cut the Persona off with something still to say.

    The count behind the rate below, and the two are derived from one pass so
    they can never disagree. What counts as an interruption is decided in
    `interruptions.py`; in particular a short listening signal and a start made
    as the line was ending anyway are not one.

    Nothing here says that interrupting is wrong. Cutting in on a caller who is
    repeating themselves is often the right move, and this trainer supports
    barge-in deliberately. The number says how often it happened.
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


def describe_loudness_course(curve: Sequence[float | None]) -> str:
    """F-37's curve as one sentence for the wrap-up prompt.

    Positions are thirds of the user's *own speaking time*, never a timestamp:
    session/models.py concatenates their Turns and inserts nothing for the
    Persona's, so this clock and the transcript's do not agree.
    """
    audible = sorted(value for value in curve if value is not None)
    if len(audible) < _MIN_STRETCH_POINTS:
        return "Loudness course: too little audible speech to describe."

    stretches = _find_stretches(_smooth(curve), _band(audible))
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
    """The call's own middle ground: its median, widened by its own spread.

    Median absolute deviation, not a percentile band: a stretch covering a third
    of the call *is* the tenth percentile, so a percentile band went blind to
    the long shifts that matter most (measured, between a fifth and a third).
    The MAD survives anything short of half the call. A zero median deviation
    falls back to the mean, which vanishes only for a constant curve.
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
    its length -- as (direction, index of its peak).

    A call held evenly yields none: the band comes from its own samples, so a
    steady speaker never leaves it. A flat call must not be given a variation.
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
    # Active -- F-53's Kennzahlen, plus F-37's loudness curve. No metric
    # carries a target range: there is no validated norm for this population,
    # and a made-up threshold is a score in disguise (ADR 0004/0051).
    #
    # `aspect` splits them into the two halves the screen shows one at a time.
    # Redeanteil is `what` despite coming from durations: it describes the
    # shape of the exchange, not the delivery.
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
