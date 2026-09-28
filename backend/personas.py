"""The Persona value objects the backend works with (loaded via `backend/library.py`,
ADR 0041), kept free of database access for `backend/session/`.

Prompt fields are English, display fields in the UI language, `language_id` is what the
Persona speaks (ADR 0043). A Persona carries the *manner*, never the situation (ADR 0045)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PersonaVoice:
    """How this Persona sounds. One field, because there is one speech
    backend (ADR 0103); it stays a value type rather than a bare int so a
    second voice parameter has somewhere to go."""

    kugelaudio_voice_id: int


# A record, not an object with behaviour: every field is one column of the
# `persona` row, and the display/prompt split (ADR 0043) means most of them come
# in pairs. Grouping them into sub-objects would add indirection without
# removing a single field.
@dataclass(frozen=True)
class Persona:  # pylint: disable=too-many-instance-attributes
    # `id` is the row's `extern_id` (ADR 0050/0058), the value the client sends
    # back in `session.start`.
    id: str
    name: str
    language_id: str
    language_name: str
    voice: PersonaVoice
    # Display: shown on the selection card.
    role_label: str
    # Display: the same character sketch as `traits`, in the UI language,
    # for the info panel behind the card. None if the seed carries none.
    traits_label: str | None
    # Display: what this Persona is meant to train. German already, and read
    # by nothing else -- it describes the exercise, not the character, so the
    # system prompt must never receive it.
    training_goal: str
    # Prompt: English, read only by the system prompt.
    role: str
    traits: str
    behavior: str
    # The objections this Persona tends to raise (R-12, ADR 0045). Ordered,
    # English, and phrased as moves rather than as quotable lines: the model
    # reuses quoted examples verbatim, and `persona_einwand` has no language
    # column while a Persona's language is fixed. A tuple because the Persona
    # is frozen.
    objections: tuple[str, ...] = ()
    # Display counterpart of `objections`: the same moves in the UI language,
    # same order, same length. Built in one pass in `library._to_persona`, so
    # an objection and its label cannot fall out of step.
    objection_labels: tuple[str, ...] = ()
    # Display: the path this Persona's portrait is served from. Defaulted
    # rather than required, because it is display-only -- a Persona without a
    # picture plays exactly the same, and the UI shows its initials instead.
    avatar_url: str | None = None
