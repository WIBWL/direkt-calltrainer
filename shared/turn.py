"""The Turn timeline a running call writes and the analysis reads back. Imports
nothing from `shared.feedback` but `acoustics` (ADR 0090)."""

from dataclasses import dataclass, field

from shared.feedback.acoustics import Pause


@dataclass
class Turn:  # pylint: disable=too-many-instance-attributes
    """One exchange (CONTEXT.md); stored as one row per speaker."""

    seq: int
    persona_text: str = ""
    user_text: str = ""
    # Only `utterances()` reads it, to mark the transcript line (ADR 0035).
    persona_interrupted: bool = False
    # Synthesized but never played; kept out of `persona_text` and the history.
    persona_unheard: str = ""

    # Milliseconds from Session start. The Persona's window is modelled from its
    # synthesized audio; the user's runs from first sound to last (ADR 0114).
    user_offset_ms: int | None = None
    user_end_ms: int | None = None
    persona_offset_ms: int | None = None
    # Where the Persona stopped being heard (trimmed on barge-in).
    persona_end_ms: int | None = None
    # Where it would have stopped untrimmed. F-51 reads this, talk share the
    # heard end; reading F-51 off the trimmed end measures VAD delay instead.
    persona_dispatched_end_ms: int | None = None

    # Already rebased onto the Session timeline. `user_speech_ms` includes VAD
    # padding, so no figure divides by it (ADR 0114).
    user_speech_ms: int = 0
    user_phonation_ms: int = 0
    # False once any fragment failed to measure (ADR 0048).
    user_acoustics_complete: bool = True
    pauses: list[Pause] = field(default_factory=list)
    loudness_db: list[float | None] = field(default_factory=list)
    pitch_hz: list[float | None] = field(default_factory=list)
