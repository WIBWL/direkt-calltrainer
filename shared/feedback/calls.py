"""The readings of a finished call: `utterances` on a timeline, `conversation`
folded into the facts every metric reads. The dependency on `Turn` runs one way
(ADR 0090)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from shared.feedback.acoustics import Pause, TurnFacts
from shared.feedback.interruptions import Segment
from shared.turn import Turn


@dataclass(frozen=True)
class Utterance:
    speaker: Literal["user", "persona"]
    text: str
    offset_ms: int
    duration_ms: int | None
    # A field beside the marker in `text`, so nothing has to match the string.
    interrupted: bool = False
    unheard: str = ""
    # Persona only: how long the audio would have run untrimmed. None falls
    # back to `duration_ms`.
    dispatched_ms: int | None = None
    # Carried because the stored row is written from an Utterance (ADR 0081).
    acoustics: TurnFacts | None = None


def utterances(turns: Sequence[Turn]) -> list[Utterance]:
    """Single-speaker utterances in spoken order: within a Turn the user speaks
    first. The one place that knows this ordering."""
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
    """None if nothing was measured; `complete=False` means partly measured."""
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
    """`at_ms` is where the reply began, on the transcript's clock."""

    at_ms: int
    gap_ms: int


@dataclass(frozen=True)
class Conversation:  # pylint: disable=too-many-instance-attributes  # a record of measured facts, one field per fact
    """A finished call reduced to the facts the metrics take (ADR 0051)."""

    user_text: str = ""
    # None: the vocabulary metrics drop out.
    language_id: str | None = None
    reverse: bool = False
    user_phonation_ms: int = 0
    user_acoustics_complete: bool = True
    persona_speech_ms: int = 0
    # Located events, so the page can show which question a silence preceded.
    reactions: tuple[Reaction, ...] = ()
    pauses: tuple[Pause, ...] = ()
    loudness_db: tuple[float | None, ...] = ()
    # 10 ms grid, finer than loudness: 100 ms aliases intonation's movement.
    pitch_hz: tuple[float | None, ...] = ()
    # Per utterance, for the terminal contours.
    pitch_per_turn: tuple[tuple[float | None, ...], ...] = ()
    # (text, phonation ms) per utterance: the opening and F-53's run count.
    user_turns: tuple[tuple[str, int], ...] = ()
    persona_turns: int = 0
    # Empty when no side was measured; no overlap can be established then.
    timeline: tuple[Segment, ...] = ()

    @property
    def user_voiced_ms(self) -> int:
        """Phonation plus inner pauses: first sound to last, without VAD padding
        (ADR 0114). Both terms are stored, so live and stored calls agree."""
        return self.user_phonation_ms + sum(pause.duration_ms for pause in self.pauses)


def conversation(
    turns: Sequence[Turn], language_id: str | None = None, reverse: bool = False
) -> Conversation:
    """Reaction time runs from the previous Persona line's end, keeping model
    latency out of the window (ADR 0051)."""
    reactions: list[Reaction] = []
    pauses: list[Pause] = []
    loudness: list[float | None] = []
    pitch: list[float | None] = []
    user_phonation = persona_ms = persona_turns = 0
    persona_stopped: int | None = None

    for turn in turns:
        # An unmeasured Turn's offset is the speech's end; it would read as hesitation.
        if (turn.user_acoustics_complete and
                turn.user_offset_ms is not None and
                persona_stopped is not None):
            reactions.append(
                Reaction(turn.user_offset_ms, max(0, turn.user_offset_ms - persona_stopped))
            )
        user_phonation += turn.user_phonation_ms
        pauses.extend(turn.pauses)
        loudness.extend(turn.loudness_db)
        pitch.extend(turn.pitch_hz)
        # A reply nobody heard was dropped (ADR 0035) and must not count.
        if turn.persona_text:
            persona_ms += _span(turn.persona_offset_ms, turn.persona_end_ms) or 0
            persona_turns += 1
        persona_stopped = turn.persona_end_ms or persona_stopped

    return Conversation(
        user_text=" ".join(turn.user_text for turn in turns if turn.user_text),
        language_id=language_id,
        reverse=reverse,
        user_phonation_ms=user_phonation,
        user_acoustics_complete=all(
            turn.user_acoustics_complete for turn in turns if turn.user_text
        ),
        persona_speech_ms=persona_ms,
        reactions=tuple(reactions),
        pauses=tuple(pauses),
        loudness_db=tuple(loudness),
        pitch_hz=tuple(pitch),
        pitch_per_turn=tuple(tuple(turn.pitch_hz) for turn in turns if turn.pitch_hz),
        user_turns=tuple(
            (turn.user_text, turn.user_phonation_ms) for turn in turns if turn.user_text
        ),
        persona_turns=persona_turns,
        timeline=timeline(turns),
    )


def timeline(turns: Sequence[Turn]) -> tuple[Segment, ...]:
    """Unmeasured sides are dropped: a guessed duration would invent overlap."""
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
    return None if start is None or end is None else max(0, end - start)
