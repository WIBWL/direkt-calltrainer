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
# pylint: disable=too-many-instance-attributes  # A value object: the columns
# `library.py` maps, not behaviour. Splitting it would only move fields around.
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
    # Display: the same situation and case facts in the UI language, for the
    # read view behind a card (ADR 0076). None on an authored Scenario, which
    # is already written in its author's language.
    description_label: str | None = None
    case_facts_label: str | None = None
    # Display: the trainee's own briefing, in the UI language (ADR 0054) --
    # role, room for manoeuvre, what a good outcome is. Never handed to the
    # model: the objective is the trainee's, and giving it to the caller is the
    # defect ADR 0045 removed. Empty means a Scenario that briefs nobody.
    briefing: str = ""
    # Display/filter only, never part of the prompt (ADR 0072): one of
    # `backend.db.models.SCENARIO_CATEGORIES`, or None for a Scenario that
    # carries no category. F-03's three call contexts, made selectable.
    category: str | None = None
    # Authorship (ADR 0058) and visibility (`private`/`tenant`/`public`; `tenant`
    # is ADR 0060). Carried so `backend/api/scenarios.py` can badge a card and
    # gate editing; `library.py` always sets both. The defaults are a built-in.
    created_by: str | None = None
    visibility: str = "public"
    # Drafted from a finished Session's feedback rather than written by hand
    # (ADR 0069). Its own category in the library, not an authorship of its own:
    # the User owns it exactly as if they had written it.
    follow_up: bool = False
