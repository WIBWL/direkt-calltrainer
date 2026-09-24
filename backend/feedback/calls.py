"""The two readings of a finished call, and the record the statistics come from.
`utterances` puts what was said on a timeline; `conversation` folds the Turns
into the facts every derivation reads. `Turn` stays in `session/models.py` and
knows nothing about this package, so the dependency runs one way.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from backend.feedback.acoustics import Pause, TurnFacts
from backend.feedback.interruptions import Segment
from backend.session.models import Turn


@dataclass(frozen=True)
class Utterance:
    """One side of one exchange, on the Session's timeline."""

    speaker: Literal["user", "persona"]
    text: str
    offset_ms: int
    duration_ms: int | None
    # True on a Persona line cut back to the heard part (ADR 0035). Carried as
    # a field beside the visible marker in `text`, so that anything computing
    # on it does not have to match a string (F-51).
    interrupted: bool = False
    # The words that were cut off, for the wrap-up's drill-down. Empty
    # everywhere else.
    unheard: str = ""
    # How long this side's audio would have run had nobody cut in. Persona
    # lines only, and equal to `duration_ms` unless the reply was trimmed --
    # `duration_ms` is what was heard, this is what was sent (F-51 against
    # F-53, see `session.models.Turn`). None where the Turn predates the
    # distinction, and every reader falls back to `duration_ms` there.
    dispatched_ms: int | None = None
    # The raw paraverbal facts of a user line (ADR 0081), carried because the
    # stored row is written from an Utterance. None on a Persona line and on a
    # user line with no measurement behind it.
    acoustics: TurnFacts | None = None


def utterances(turns: Sequence[Turn]) -> list[Utterance]:
    """The exchanges flattened into single-speaker utterances, in the order spoken.
    Within one Turn the user speaks first (replying to the previous Persona line);
    empty sides are skipped, a cut-off Persona line ends with "[unterbrochen]"
    (ADR 0035). The one place that knows this ordering.
    """
    spoken: list[Utterance] = []
    for turn in turns:
        if turn.user_text:
            spoken.append(Utterance(
                "user", turn.user_text, turn.user_offset_ms or 0,
                _span(turn.user_offset_ms, turn.user_end_ms),
                acoustics=facts(turn),
            ))
        if turn.persona_text:
            text = turn.persona_text
            if turn.persona_interrupted:
                text = f"{text} ... [unterbrochen]"
            spoken.append(Utterance(
                "persona", text, turn.persona_offset_ms or 0,
                _span(turn.persona_offset_ms, turn.persona_end_ms),
                interrupted=turn.persona_interrupted,
                unheard=turn.persona_unheard,
                dispatched_ms=_span(turn.persona_offset_ms, turn.persona_dispatched_end_ms),
            ))
    return spoken


def facts(turn: Turn) -> TurnFacts | None:
    """The raw paraverbal facts of one Turn's user side, or None if there was
    no measurement behind it (ADR 0081). `complete` is a different statement:
    the Turn *was* measured, and part of it failed.
    """
    if not turn.user_speech_ms and not turn.loudness_db and not turn.pauses:
        return None
    return TurnFacts(
        speech_ms=turn.user_speech_ms,
        phonation_ms=turn.user_phonation_ms,
        complete=turn.user_acoustics_complete,
        pauses=tuple(turn.pauses),
        loudness_db=tuple(turn.loudness_db),
    )


@dataclass(frozen=True)
class Reaction:
    """One silence between the Persona falling silent and the user replying.
    `at_ms` is where the reply began, the same offset the stored transcript
    carries, so the exchange can be shown without matching two clocks.
    """

    at_ms: int
    gap_ms: int


@dataclass(frozen=True)
class Conversation:  # pylint: disable=too-many-instance-attributes  # a record of measured facts, one field per fact
    """One finished call, reduced to the facts the statistics are derived from.
    Built by `conversation()`, which keeps the machine's latency out of both
    speakers' windows (ADR 0051); the one input every derivation takes.
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
    # counted from the moment the Persona stopped speaking, and when that
    # reply began. Located like a Pause rather than a bare length, so the
    # figure's own page can show *which* question the longest silence stood
    # in front of (ADR 0098). A located event, not a per-Turn statistic.
    reactions: tuple[Reaction, ...] = ()
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


def conversation(
    turns: Sequence[Turn], language_id: str | None = None, reverse: bool = False
) -> Conversation:
    """Fold the finished call into the facts its statistics are derived from.
    `language_id` is the Persona's; without it the vocabulary readings drop out.
    Reaction time runs from the end of Turn N-1's Persona line, so the machine's
    latency is outside the window (ADR 0051).
    """
    reactions: list[Reaction] = []
    pauses: list[Pause] = []
    loudness: list[float | None] = []
    pitch: list[float | None] = []
    user_ms = user_phonation = persona_ms = persona_turns = 0
    persona_stopped: int | None = None

    for turn in turns:
        # An unmeasured Turn's offset is the *end* of the user's speech, which
        # read as a reaction time would be inflated by the whole utterance.
        if (turn.user_acoustics_complete and
                turn.user_offset_ms is not None and
                persona_stopped is not None):
            reactions.append(
                Reaction(turn.user_offset_ms, max(0, turn.user_offset_ms - persona_stopped))
            )
        user_ms += turn.user_speech_ms
        user_phonation += turn.user_phonation_ms
        pauses.extend(turn.pauses)
        loudness.extend(turn.loudness_db)
        pitch.extend(turn.pitch_hz)
        # Gated on the text: a reply talked over before any of it was heard is
        # dropped from the Transcript (ADR 0035) and must not count towards
        # Redeanteil's denominator. Trimmed replies already end where played.
        if turn.persona_text:
            persona_ms += _span(turn.persona_offset_ms, turn.persona_end_ms) or 0
            persona_turns += 1
        persona_stopped = turn.persona_end_ms or persona_stopped

    return Conversation(
        user_text=" ".join(turn.user_text for turn in turns if turn.user_text),
        language_id=language_id,
        reverse=reverse,
        user_speech_ms=user_ms,
        user_phonation_ms=user_phonation,
        # Only Turns the user spoke in: the opening Turn has no audio to measure.
        user_acoustics_complete=all(
            turn.user_acoustics_complete for turn in turns if turn.user_text
        ),
        persona_speech_ms=persona_ms,
        reactions=tuple(reactions),
        pauses=tuple(pauses),
        loudness_db=tuple(loudness),
        pitch_hz=tuple(pitch),
        # Grouped by utterance as well, which the terminal contours read:
        # where one sentence ended is not recoverable from the flat curve.
        pitch_per_turn=tuple(tuple(turn.pitch_hz) for turn in turns if turn.pitch_hz),
        # The utterances the user actually spoke in, which is the set
        # `user_acoustics_complete` is taken over: the opening reading needs
        # their text and length, F-53's Sprechlänge only how many there are.
        user_turns=tuple(
            (turn.user_text, turn.user_phonation_ms) for turn in turns if turn.user_text
        ),
        persona_turns=persona_turns,
        timeline=timeline(turns),
    )


def timeline(turns: Sequence[Turn]) -> tuple[Segment, ...]:
    """The call as bare segments, for the overlap classification (F-51).
    Unmeasured sides are dropped: guessing a duration would invent the very
    overlap being measured.
    """
    return tuple(
        Segment(
            speaker=spoken.speaker,
            offset_ms=spoken.offset_ms,
            duration_ms=spoken.duration_ms,
            interrupted=spoken.interrupted,
            dispatched_ms=spoken.dispatched_ms,
        )
        for spoken in utterances(turns)
        if spoken.duration_ms
    )


def _span(start: int | None, end: int | None) -> int | None:
    """How long an utterance lasted, where both of its ends are known."""
    return None if start is None or end is None else max(0, end - start)
