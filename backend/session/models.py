"""Session data, the Turn timeline, and the internal event union yielded by
SessionOrchestrator.run_turn.

The events are internal — `backend/api/session_ws.py` is their only consumer,
turning each into one wire message. Separate types, not dicts, so a missing
branch there is obvious.

This module owns the two readings of a finished Session: `utterances` puts what
was said on a timeline, and `conversation` folds the measurements into the
facts the Session's statistics are derived from. Both live here because both
are questions about a *sequence* of Turns, which is what a Turn's fields alone
cannot answer.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from backend.feedback.acoustics import Pause, TurnFacts
from backend.feedback.interruptions import Segment
from backend.feedback.metrics import Conversation


@dataclass
class Turn:  # pylint: disable=too-many-instance-attributes
    """One exchange within a Session (see CONTEXT.md). Distinct from the
    persisted `turn` row (ADR 0026), which is one utterance of one speaker."""

    seq: int
    persona_text: str = ""
    user_text: str = ""
    # True once the user talked over this Turn's Persona reply and only the
    # heard part was kept (ADR 0035). Kept off `persona_text` so the LLM history
    # and the metrics never see it -- `utterances()` is the only reader, adding
    # the visible "[unterbrochen]" marker to the transcript line.
    persona_interrupted: bool = False
    # What had been synthesized but not yet played when the user cut in (F-51).
    # Kept out of `persona_text` and out of the model's history on purpose
    # (ADR 0035 keeps both to the heard words); it exists so the wrap-up can
    # show what the Persona had been about to say.
    persona_unheard: str = ""

    # The two utterances placed on the Session's timeline, in milliseconds from
    # its start; None until that utterance has happened. The Persona's window is
    # modelled from the audio synthesized for it, because the server never
    # learns when the client finished playing it.
    user_offset_ms: int | None = None
    user_end_ms: int | None = None
    persona_offset_ms: int | None = None
    persona_end_ms: int | None = None

    # Paraverbal facts about the user's speech (ADR 0048), taken while the
    # audio was still in memory and already rebased onto the Session's
    # timeline -- so a Turn reopened after a barge-in, and therefore spoken in
    # several fragments, needs no special case once the Session is folded up.
    #
    # How long the recording ran, and how much of that was speech rather than
    # silence. Redeanteil divides by the first (the Persona's side is audio
    # duration too), Sprechtempo by the second.
    user_speech_ms: int = 0
    user_phonation_ms: int = 0
    # False once any fragment of this Turn failed to measure: its words still
    # count while its milliseconds do not, so the figures above are short by an
    # unknown amount and `user_offset_ms` is a fallback rather than a reading.
    user_acoustics_complete: bool = True
    pauses: list[Pause] = field(default_factory=list)
    loudness_db: list[float | None] = field(default_factory=list)
    # The pitch curve on the same grid as the loudness one (F-35), so the two
    # concatenate identically across Turns.
    pitch_hz: list[float | None] = field(default_factory=list)


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
    # The raw paraverbal facts of this utterance, on a user line only (ADR
    # 0081). Carried through the flattening because the row is written from an
    # Utterance: without it the facts would stop at `conversation()`, which
    # folds the whole call into one set and is the only other reader of a Turn.
    #
    # None on a Persona line and on a user line with no measurement behind it.
    acoustics: TurnFacts | None = None


def utterances(turns: Sequence[Turn]) -> list[Utterance]:
    """The exchanges flattened into single-speaker utterances, in the order spoken.

    Within one Turn the user speaks first: their text is the reply to the
    *previous* Turn's Persona line, and this Turn's Persona line answers it.
    Empty sides are skipped -- the opening Turn has no user text, and an
    interrupted one may have no Persona text. A Persona line the user cut off
    ends with a visible "[unterbrochen]" marker (ADR 0035).

    The single place that knows this ordering: both the Transcript sent over
    the WebSocket and the persisted Turn rows are built from it.
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
            ))
    return spoken


def facts(turn: Turn) -> TurnFacts | None:
    """The raw paraverbal facts of one Turn's user side, or None if there was
    no measurement behind it (ADR 0081).

    "No measurement" is a Turn with no speaking time and no curve, which is
    what an unmeasurable recording leaves. `complete` is a different statement
    and is carried: the Turn *was* measured, and part of it failed.
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


def conversation(
    turns: Sequence[Turn], language_id: str | None = None, reverse: bool = False
) -> Conversation:
    """Fold the finished call into the facts its statistics are derived from.

    `language_id` is the Persona's. Optional: without it only the readings
    that need a vocabulary drop out.

    Reaction time is the one measure that spans two Turns: the user's reply in
    Turn N answers the Persona line of Turn N-1, so it is counted from that
    line's end. Everything the machine did in between -- generating, then
    synthesizing -- is outside the window by construction (ADR 0051).
    """
    reactions: list[int] = []
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
            reactions.append(max(0, turn.user_offset_ms - persona_stopped))
        user_ms += turn.user_speech_ms
        user_phonation += turn.user_phonation_ms
        pauses.extend(turn.pauses)
        loudness.extend(turn.loudness_db)
        pitch.extend(turn.pitch_hz)
        persona_ms += _span(turn.persona_offset_ms, turn.persona_end_ms) or 0
        persona_stopped = turn.persona_end_ms or persona_stopped
        if turn.persona_text:
            persona_turns += 1

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
        reactions_ms=tuple(reactions),
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

    The same flattening `utterances()` does, minus the text and with unmeasured
    sides dropped: a segment with no duration cannot be tested for overlap, and
    guessing one would invent the very thing being measured.
    """
    return tuple(
        Segment(
            speaker=spoken.speaker,
            offset_ms=spoken.offset_ms,
            duration_ms=spoken.duration_ms,
            interrupted=spoken.interrupted,
        )
        for spoken in utterances(turns)
        if spoken.duration_ms
    )


def _span(start: int | None, end: int | None) -> int | None:
    """How long an utterance lasted, where both of its ends are known."""
    return None if start is None or end is None else max(0, end - start)


@dataclass
class StateChanged:
    """The state the client animation should show. `speaking` waits for real
    audio, so the animation never claims speech during a silent gap."""

    state: Literal["listening", "thinking", "speaking"]


@dataclass
class AudioChunk:
    """One synthesised piece of a reply; a Turn emits several, played back to back."""

    turn_seq: int
    chunk_seq: int
    audio: bytes


@dataclass
class TurnCompleted:
    """The Turn finished cleanly. `ends_call` also ends the Session — goodbye,
    a detected closing signal, or a degenerate reply (ADR 0037, ADR 0038)."""

    turn_seq: int
    ends_call: bool = False


@dataclass
class Failed:
    """A leg failed past its one retry (ADR 0016); the Session then ends, with
    no per-Turn recovery. Distinct codes so the client can word each leg."""

    code: Literal["stt_failed", "llm_failed", "tts_failed"]
    message: str


# `_forward_turn_events` in session_ws.py has one branch per member — a new
# member needs a branch there or its events are silently dropped.
TurnEvent = StateChanged | AudioChunk | TurnCompleted | Failed
