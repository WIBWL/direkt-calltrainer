"""The Scenario value object the backend works with.

The Scenarios themselves live in the database and are loaded through
`backend/library.py` (ADR 0041); this module only defines their shape.

A Scenario has no language of its own (ADR 0043): the prompt fields are the
English call context handed to the model, `short_description` the teaser shown
in the UI. That is what lets any Persona run any Scenario regardless of the
language the Persona speaks -- and ADR 0045 keeps it that way by putting the
case here, stated about the case rather than about whoever is calling.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    id: str
    name: str
    # Display: the one-line teaser on the selection card.
    short_description: str
    # Prompt: English call context -- the situation alone (ADR 0045).
    description: str
    # Prompt: the case itself (ADR 0045). Facts of the case, what the caller
    # wants out of the call, and the condition under which the caller counts
    # the matter as settled. Empty is allowed and means "improvise", which is
    # what a Scenario predating ADR 0045 -- or a user-authored one (ADR 0024)
    # -- looks like.
    case_facts: str = ""
    call_goal: str = ""
    success_condition: str = ""
    # A loose category label (e.g. "Preisgespräch"). Authored rows set it too;
    # nothing in the prompt reads it, so it stays optional.
    scenario_type: str = ""
    # Authorship (ADR 0058) and visibility (`private`/`tenant`/`public`; `tenant`
    # is ADR 0060). Carried so `backend/api/scenarios.py` can badge a card and
    # gate editing; `library.py` always sets both. The defaults are a built-in.
    created_by: str | None = None
    visibility: str = "public"
