"""Turn/Session data and the internal event union yielded by SessionOrchestrator.run_turn."""

from dataclasses import dataclass


@dataclass
class Turn:
    """One exchange within a Session: the user's utterance and the Persona's
    reply to it (see CONTEXT.md's "Turn" entry)."""

    seq: int
    user_text: str = ""
    persona_text: str = ""


@dataclass
class StateChanged:
    """The Session's conversation state changed (drives the client's animation)."""

    state: str  # "listening" | "thinking" | "speaking"


@dataclass
class AudioChunk:
    """One synthesized TTS chunk of the Persona's reply, ready to send."""

    turn_seq: int
    chunk_seq: int
    audio: bytes


@dataclass
class TurnCompleted:
    """The current Turn finished successfully; no more chunks will follow."""

    turn_seq: int
    ends_call: bool = False
    """True if the Persona (or the user, via the Persona's reply to a
    farewell) naturally concluded the call — the Session should end here
    rather than return to listening for another Turn."""


@dataclass
class Failed:
    """A pipeline leg failed past its retry; the Session should end gracefully."""

    code: str  # "stt_failed" | "llm_failed" | "tts_failed"
    message: str


# Union of events a Turn can produce, translated to wire messages by session_ws.py.
TurnEvent = StateChanged | AudioChunk | TurnCompleted | Failed
