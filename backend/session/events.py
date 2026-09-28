"""The internal event union yielded by SessionOrchestrator.run_turn (consumed
only by `backend/api/session_ws.py`). The Turn itself is `shared/turn.py`."""

from dataclasses import dataclass
from typing import Literal


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
