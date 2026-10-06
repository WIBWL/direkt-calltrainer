"""Persona value objects, free of database access for `backend/session/`.
Prompt fields are English, display fields German (ADR 0043)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PersonaVoice:
    """A value type, so a second voice parameter has somewhere to go."""

    kugelaudio_voice_id: int


@dataclass(frozen=True)
class Persona:  # pylint: disable=too-many-instance-attributes  # one field per column
    # The row's `extern_id` (ADR 0050).
    id: str
    name: str
    language_id: str
    language_name: str
    voice: PersonaVoice
    # Display:
    role_label: str
    traits_label: str | None
    # Never given to the model.
    training_goal: str
    # Prompt (English):
    role: str
    traits: str
    behavior: str
    # Moves, not quotable lines (ADR 0045).
    objections: tuple[str, ...] = ()
    # Same order and length as `objections`.
    objection_labels: tuple[str, ...] = ()
    # Picks the anti-repeat nudge that offers no ground.
    hard: bool = False
    avatar_url: str | None = None
