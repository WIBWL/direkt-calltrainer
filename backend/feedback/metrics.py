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
from collections.abc import Callable
from dataclasses import dataclass
from statistics import fmean

from backend.feedback.acoustics import Pause

_MS_PER_MINUTE = 60_000
_MS_PER_SECOND = 1000
# Words, for rate denominators: letter runs, so punctuation and the digits STT
# writes for numbers don't inflate the count.
_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)
_SENTENCE_END_RE = re.compile(r"[.!?]+")


@dataclass(frozen=True)
class Conversation:
    """One finished call, reduced to the facts the statistics are derived from.

    Assembled by backend/session/models.py, which owns the Turn timeline and
    keeps the machine's latency out of both speakers' windows (ADR 0051).
    """

    user_text: str = ""
    user_speech_ms: int = 0
    # Only ever a denominator, for the user's share of the speaking time.
    persona_speech_ms: int = 0
    # One entry per exchange: how long the user took to start replying,
    # counted from the moment the Persona stopped speaking.
    reactions_ms: tuple[int, ...] = ()
    # Silent stretches inside the user's own speech, on the Session's timeline.
    pauses: tuple[Pause, ...] = ()
    # The user's loudness across the whole call, at acoustics.py's fixed rate.
    loudness_db: tuple[float | None, ...] = ()


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
    time, not wall-clock, so the model's own latency dilutes neither share."""
    spoken = call.user_speech_ms + call.persona_speech_ms
    # Words with no measured speaking time behind them mean the measurement
    # failed (ADR 0048), not that the speaker stayed silent. Reporting the
    # share anyway would put a 0% or a 100% in front of the user as though it
    # had been measured -- exactly what `measure` refuses to do elsewhere.
    if not spoken or (call.user_text and not call.user_speech_ms):
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
    """
    words = _count_words(call.user_text)
    if not words:
        return None
    questions = call.user_text.count("?")
    return Measurement("questions", float(questions), {"per_100_words": questions * 100 / words})


def _pace(call: Conversation) -> Measurement | None:
    """F-36. Words per minute of speaking time, since that is the unit the user
    thinks in. The gaps between utterances are excluded, so this says how fast
    they talk rather than how much of the call they filled.

    F-36 also asks for the rate "relativ zum Gesprächspartner". That partner is
    a synthesized voice reading at whatever rate the TTS model was configured
    for, so the comparison would measure a setting, not the user; it is left
    out until the partner is a person.

    Note what the denominator contains: the client's VAD pads each recording
    with its pre-speech and redemption frames, so `user_speech_ms` runs a few
    hundred milliseconds long per utterance and this rate reads slightly slow.
    """
    words = _count_words(call.user_text)
    if not words or not call.user_speech_ms:
        return None
    return Measurement("pace", words * _MS_PER_MINUTE / call.user_speech_ms)


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


def _pauses(call: Conversation) -> Measurement | None:
    """F-51. Average length of a silent stretch inside the user's own speech.

    Only pauses within an utterance count. A hesitation long enough to trip the
    client's VAD ends the Turn instead and is measured as reaction time.
    """
    if not call.pauses:
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


def _loudness(call: Conversation) -> Measurement | None:
    """F-37. Dynamic range across the whole call as the measure of vocal
    presence, with the curve behind it. A range rather than a level, for the
    reason given on TurnAcoustics.loudness_db (ADR 0047)."""
    audible = sorted(v for v in call.loudness_db if v is not None)
    if len(audible) < 3:
        return None
    margin = len(audible) // 20  # 5th to 95th percentile, ignoring the extremes
    return Measurement(
        "loudness",
        audible[-1 - margin] - audible[margin],
        {"curve_db": list(call.loudness_db)},
    )


# --- Inventory ------------------------------------------------------------

METRICS: tuple[MetricDef, ...] = (
    # Active -- F-53's Kennzahlen, plus F-37's loudness curve. No metric
    # carries a target range: there is no validated norm for this population,
    # and a made-up threshold is a score in disguise (ADR 0004/0051).
    MetricDef("talk_share", "Redeanteil", "%", "F-24", True, _talk_share),
    MetricDef("questions", "Fragen an den Gesprächspartner", "Anzahl", "F-41", True, _questions),
    MetricDef("pace", "Sprechtempo", "Wörter/min", "F-36", True, _pace),
    MetricDef("word_count", "Gesprochene Wörter", "Wörter", "F-08", True, _word_count),
    MetricDef("reaction_time", "Reaktionszeit", "s", "F-53", True, _reaction_time),
    MetricDef("pauses", "Sprechpausen", "s", "F-51", True, _pauses),
    MetricDef("loudness", "Lautstärke", "dB", "F-37", True, _loudness),
    # SHOULD / COULD -- seeded so the vocabulary is complete, but inactive and
    # without a derivation.
    MetricDef("concreteness", "Sprachliche Konkretheit", None, "F-40", False),
    # F-42 ships, but as prose and not as a figure: what it describes is a
    # change of register across the call's three phases, which no single value
    # carries and which would need a norm nobody measured to score. It is the
    # `phase_language` paragraph of the wrap-up (backend/feedback/generator.py).
    # The row stays inactive and seeded so the vocabulary keeps its entry.
    MetricDef("phase_appropriate_language", "Phasengerechte Sprache", None, "F-42", False),
    MetricDef("congruence", "Kongruenz von Inhalt und Stimme", None, "F-39", False),
)


def _count_words(text: str) -> int:
    return len(_WORD_RE.findall(text))
