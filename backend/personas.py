"""The Persona value objects the backend works with.

The Personas themselves live in the database and are loaded through
`backend/library.py` (ADR 0041); this module only defines their shape, so
that `backend/session/` can depend on it without pulling in database access.

Two kinds of text hang off a Persona (ADR 0043): the prompt fields the model
reads, which are English, and the display fields the setup UI shows, which are
in the UI language. `language_id` names neither of those — it is the language
the Persona actually speaks in.

A Persona carries the *manner* and nothing about the situation (ADR 0045):
how it conducts itself, and the objections it tends to raise. What the call is
about belongs to the Scenario.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class PersonaVoice:
    tts_voice: str
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
