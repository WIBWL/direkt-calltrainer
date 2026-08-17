"""Session data and the internal event union yielded by SessionOrchestrator.run_turn."""

from dataclasses import dataclass
from typing import Literal


@dataclass
class Turn:
    """One exchange within a session: the persona's utterance and the user's
    reply to it (see CONTEXT.md's "Turn" entry)."""

    seq: int
    persona_text: str = ""
    user_text: str = ""


@dataclass
class StateChanged:
    """Conversation state changed."""

    state: Literal["listening", "thinking", "speaking"]


@dataclass
class AudioChunk:
    """Synthesized TTS chunk of the persona's text."""

    turn_seq: int
    chunk_seq: int
    audio: bytes


@dataclass
class TurnCompleted:
    """Turn finished successfully."""

    turn_seq: int
    ends_call: bool = False


@dataclass
class Failed:
    """A pipeline leg failed past its retry. The session should end gracefully."""

    code: Literal["stt_failed", "llm_failed", "tts_failed"]
    message: str


# Union of events a Turn can produce, translated to wire messages by session_ws.py.
TurnEvent = StateChanged | AudioChunk | TurnCompleted | Failed
