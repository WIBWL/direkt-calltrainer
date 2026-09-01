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

from backend.feedback.acoustics import Pause
from backend.feedback.metrics import Conversation


@dataclass
class Turn:
    """One exchange within a Session (see CONTEXT.md). Distinct from the
    persisted `turn` row (ADR 0026), which is one utterance of one speaker."""

    seq: int
    persona_text: str = ""
    user_text: str = ""

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
    user_speech_ms: int = 0
    pauses: list[Pause] = field(default_factory=list)
    loudness_db: list[float | None] = field(default_factory=list)


@dataclass(frozen=True)
class Utterance:
    """One side of one exchange, on the Session's timeline."""

    sprecher: Literal["nutzer", "persona"]
    text: str
    offset_ms: int
    dauer_ms: int | None


def utterances(turns: Sequence[Turn]) -> list[Utterance]:
    """The exchanges flattened into single-speaker utterances, in the order spoken.

    Within one Turn the user speaks first: their text is the reply to the
    *previous* Turn's Persona line, and this Turn's Persona line answers it.
    Empty sides are skipped -- the opening Turn has no user text, and an
    interrupted one may have no Persona text.

    The single place that knows this ordering: both the Transcript sent over
    the WebSocket and the persisted Turn rows are built from it.
    """
    spoken: list[Utterance] = []
    for turn in turns:
        if turn.user_text:
            spoken.append(Utterance(
                "nutzer", turn.user_text, turn.user_offset_ms or 0,
                _span(turn.user_offset_ms, turn.user_end_ms),
            ))
        if turn.persona_text:
            spoken.append(Utterance(
                "persona", turn.persona_text, turn.persona_offset_ms or 0,
                _span(turn.persona_offset_ms, turn.persona_end_ms),
            ))
    return spoken


def conversation(turns: Sequence[Turn]) -> Conversation:
    """Fold the finished call into the facts its statistics are derived from.

    Reaction time is the one measure that spans two Turns: the user's reply in
    Turn N answers the Persona line of Turn N-1, so it is counted from that
    line's end. Everything the machine did in between -- generating, then
    synthesizing -- is outside the window by construction (ADR 0051).
    """
    reactions: list[int] = []
    pauses: list[Pause] = []
    loudness: list[float | None] = []
    user_ms = persona_ms = 0
    persona_stopped: int | None = None

    for turn in turns:
        if turn.user_offset_ms is not None and persona_stopped is not None:
            reactions.append(max(0, turn.user_offset_ms - persona_stopped))
        user_ms += turn.user_speech_ms
        pauses.extend(turn.pauses)
        loudness.extend(turn.loudness_db)
        persona_ms += _span(turn.persona_offset_ms, turn.persona_end_ms) or 0
        persona_stopped = turn.persona_end_ms or persona_stopped

    return Conversation(
        user_text=" ".join(turn.user_text for turn in turns if turn.user_text),
        user_speech_ms=user_ms,
        persona_speech_ms=persona_ms,
        reactions_ms=tuple(reactions),
        pauses=tuple(pauses),
        loudness_db=tuple(loudness),
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
