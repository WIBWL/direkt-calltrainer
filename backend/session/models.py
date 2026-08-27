"""Session data and the internal event union yielded by SessionOrchestrator.run_turn."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass
class Turn:
    """One exchange within a session: the persona's utterance and the user's
    reply to it (see CONTEXT.md's "Turn" entry).

    Either half can stay empty: the opening Turn has no user utterance, and a
    Turn cut short by a pipeline failure (ADR 0016) has no persona reply. The
    durations are None until measured — the user's arrives from the client,
    which is the only side that knows how long the speech segment was, and the
    persona's is summed from the synthesized audio.
    """

    seq: int
    persona_text: str = ""
    user_text: str = ""
    user_duration_ms: int | None = None
    persona_duration_ms: int | None = None


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


@dataclass
class FinishedSession:
    """Everything worth persisting about a Session that has ended (ADR 0034).

    Assembled by the WebSocket layer once the call is over and handed to
    `repository.save_session` as one value, so the two sides share a single
    definition of what a stored Session consists of rather than a long
    parameter list that has to stay in the same order at both ends.
    """

    extern_id: uuid.UUID
    subject_id: str
    persona_key: str
    scenario_key: str
    language_code: str
    # How the call ended, as `session_ws` reports it: "user", "completed" or
    # "error". Mapped onto the persisted status vocabulary by the repository.
    reason: str
    started_at: datetime
    ended_at: datetime
    turns: list[Turn] = field(default_factory=list)


@dataclass
class StoredSession:
    """A Session read back out of the database.

    The counterpart to `FinishedSession`: that one goes in, this one comes out.
    It carries the Persona and Scenario by display name rather than by key,
    because its only consumer is the post-call view, which shows them.
    """

    extern_id: uuid.UUID
    persona_name: str
    scenario_name: str
    status: str
    started_at: datetime
    ended_at: datetime | None
    turns: list[Turn] = field(default_factory=list)
