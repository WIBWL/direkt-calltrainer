"""The Scenario value object the backend works with.

The Scenarios themselves live in the database and are loaded through
`backend/library.py` (ADR 0041); this module only defines their shape.

A Scenario has no language of its own (ADR 0043): `description` is the English
call context handed to the model, `short_description` the teaser shown in the
UI. That is what lets any Persona run any Scenario regardless of the language
the Persona speaks.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    id: str
    name: str
    # Display: the one-line teaser on the selection card.
    short_description: str
    # Prompt: English call context.
    description: str
