"""The Scenario value object the backend works with (loaded via `backend/library.py`,
ADR 0041). No language of its own (ADR 0043) and the case stated about the case (ADR
0045), so any Persona can run any Scenario. A *reverse* (ADR 0070) is one of these rows
too, copied from a played Scenario, plus the casting marker and the briefing."""
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class OriginSession:
    """The conversation a reverse replays, as much as a card needs (ADR 0070).
    None once that Session is deleted -- the reverse outlives it. `id` is the
    Session's `extern_id` (ADR 0050).
    """

    id: str
    persona: str
    started_at: datetime


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
    # Prompt: the case itself (ADR 0045) -- facts, and the caller's goal with the
    # condition under which it counts as settled (one merged field). Empty means
    # "improvise", as for pre-ADR-0045 or user-authored (ADR 0024) Scenarios.
    case_facts: str = ""
    call_goal: str = ""
    # Display: the same situation and case facts in the UI language, for the
    # read view behind a card (ADR 0062). None on an authored Scenario, which
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
    # A reverse (ADR 0070): the User calls, the Persona answers. Read by
    # `session/prompting.py` to swap the casting, by the wrap-up to label the
    # speakers, and by the library filter. False for everything else, and never
    # true at the same time as `follow_up` -- one is written *from* a Session,
    # the other replays one.
    reverse: bool = False
    # The conversation this reverse replays, or None -- for an ordinary
    # Scenario, and for a reverse whose origin Session has since been deleted.
    origin_session: OriginSession | None = None
    # What the User reads during a reverse call, already in German
    # (`backend/reversals.py` owns its shape). Deliberately a plain dict here:
    # nothing in the backend reads inside it, it is generated once and handed
    # to the client whole. Never given to the model.
    reverse_brief: dict | None = None
