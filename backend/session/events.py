"""The events SessionOrchestrator.run_turn yields to session_ws.py."""

from dataclasses import dataclass
from typing import Literal


@dataclass
class StateChanged:
    """`speaking` waits for real audio, so the animation never claims speech in a gap."""

    state: Literal["listening", "thinking", "speaking"]


@dataclass
class AudioChunk:
    turn_seq: int
    chunk_seq: int
    audio: bytes


@dataclass
class TurnCompleted:
    """`ends_call` also ends the Session (ADR 0037, 0038)."""

    turn_seq: int
    ends_call: bool = False


@dataclass
class Failed:
    """A leg failed past its retry (ADR 0016); the Session then ends."""

    code: Literal["stt_failed", "llm_failed", "tts_failed"]
    message: str


# `_forward_turn_events` needs a branch per member, or its events are dropped.
TurnEvent = StateChanged | AudioChunk | TurnCompleted | Failed
