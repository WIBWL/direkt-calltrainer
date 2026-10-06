"""The Scenario value object. Language-neutral (ADR 0043); a reverse (ADR 0070)
is one too, with the casting marker and briefing."""
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class OriginSession:
    """What a reverse's card shows of the Session it replays; None once deleted."""

    id: str
    persona: str
    started_at: datetime


@dataclass(frozen=True)
# pylint: disable=too-many-instance-attributes  # a value object: one field per mapped column
class Scenario:
    id: str
    name: str
    # Display:
    short_description: str
    # Prompt (English, ADR 0045):
    description: str
    # Empty means "improvise".
    case_facts: str = ""
    call_goal: str = ""
    # German display twins; None on authored rows.
    description_label: str | None = None
    case_facts_label: str | None = None
    # For the trainee only, never the model (ADR 0054).
    briefing: str = ""
    # Display and filter only (ADR 0072).
    category: str | None = None
    # The defaults describe a built-in.
    created_by: str | None = None
    visibility: str = "public"
    # Drafted from feedback (ADR 0069); owned like a hand-written row.
    follow_up: bool = False
    # Never true together with `follow_up`.
    reverse: bool = False
    # None for an ordinary Scenario or a reverse whose origin was deleted.
    origin_session: OriginSession | None = None
    # Handed to the client whole; never given to the model.
    reverse_brief: dict | None = None
