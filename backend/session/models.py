"""Session data, the Turn timeline, and the internal event union yielded by
SessionOrchestrator.run_turn (consumed only by `backend/api/session_ws.py`).

What a running call writes; readings of a finished one live in `backend/feedback/calls.py`.
Nothing here may import from `backend.feedback` except `acoustics` (test_module_dependencies)."""

from dataclasses import dataclass, field
from typing import Literal

from backend.feedback.acoustics import Pause


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
    # Where the Persona's audio stopped being *heard*: the end of what was
    # dispatched, or the played position where a barge-in cut it (ADR 0035).
    # This is the speaking time the metrics divide by.
    persona_end_ms: int | None = None
    # Where it would have stopped had nobody cut in; never trimmed. Two fields
    # because F-51 asks how much audio was *sent* and F-53's Redeanteil how long
    # it was *heard*: reading F-51 off the trimmed end measures the browser's
    # voice-detection delay instead ("0.7 seconds left" of a nine-second reply).
    persona_dispatched_end_ms: int | None = None

    # Paraverbal facts about the user's speech (ADR 0048), already rebased onto
    # the Session's timeline, so a Turn spoken in several fragments needs no
    # special case. Talk share divides by the recording length, pace by phonation.
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
