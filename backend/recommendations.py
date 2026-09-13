"""Which Scenarios to suggest first, from what a User said about their work (F-62).

Rule-based, and every suggestion says why it was made, so the screen can show
the reason rather than ask to be trusted. Suggesting a Scenario to practise a
goal claims nothing about how the User does at it (ADR 0076).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from backend import focus, library
from backend.db.session import session_scope

# One row of the grid in front of the "show all" tile.
MAX_RECOMMENDATIONS = 5

# The call context that exercises a focus goal. The voice goals are absent on
# purpose: every Scenario trains the voice, so they cannot steer the choice.
GOAL_CATEGORIES: dict[str, tuple[str, ...]] = {
    "objection_handling": ("closing",),
    "closing": ("closing",),
    "needs_analysis": ("requirements",),
    "active_listening": ("requirements",),
    "composure": ("operations", "pricing"),
    "empathy": ("operations",),
}


@dataclass(frozen=True)
class Candidate:
    """What a Scenario card offers the scoring."""

    id: str
    category: str | None
    reverse: bool


@dataclass(frozen=True)
class Recommendation:
    """Why one Scenario is suggested."""

    call_type: bool          # its category is a kind of call the User takes
    goals: tuple[str, ...]   # the picked goals its context exercises


def recommend(
    candidates: Iterable[Candidate],
    categories: Iterable[str],
    goals: Iterable[str],
    played: set[str],
) -> dict[str, Recommendation]:
    """The Scenarios to suggest, by id, at most MAX_RECOMMENDATIONS.

    A call type counts 2, each goal the context exercises 1; a Scenario not yet
    played wins a tie, then the listing order. A reverse replays one particular
    call and an uncategorised Scenario has no context, so neither is suggested.
    """
    kinds, picked = set(categories), tuple(goals)
    scored = []
    for position, candidate in enumerate(candidates):
        if candidate.reverse or candidate.category is None:
            continue
        call_type = candidate.category in kinds
        matched = tuple(g for g in picked if candidate.category in GOAL_CATEGORIES.get(g, ()))
        score = 2 * call_type + len(matched)
        if score:
            scored.append((-score, candidate.id in played, position, candidate.id,
                           Recommendation(call_type, matched)))
    scored.sort()
    return {entry[3]: entry[4] for entry in scored[:MAX_RECOMMENDATIONS]}


@dataclass(frozen=True)
class Partner:
    """A Persona, as the next-call offers need it."""

    id: str
    language_id: str


@dataclass(frozen=True)
class NextCall:
    """One way to go on after a call (F-64), from the library as it stands."""

    kind: str                 # "language": the same Scenario, other language
    scenario_id: str          # "library": another Scenario, same partner
    persona_id: str
    recommendation: Recommendation | None = None
    unplayed: bool = False


@dataclass(frozen=True)
class Choices:
    """What the offers after a call are chosen from."""

    candidates: list[Candidate]
    partners: list[Partner]
    picks: dict[str, Recommendation]   # the profile's suggestions, best first
    played_ids: set[str]


def next_calls(played: Candidate, persona: Partner, choices: Choices) -> list[NextCall]:
    """At most two offers, neither needing a model: the same Scenario in the
    other language, and another Scenario -- the best suggestion not just played,
    else an unplayed one from the same category.
    """
    offers: list[NextCall] = []
    # Not for a reverse: its briefing is German prose (ADR 0070).
    other = next(
        (p for p in choices.partners if p.language_id != persona.language_id), None
    )
    if other and not played.reverse:
        offers.append(NextCall("language", played.id, other.id))
    choice = _library_choice(played, choices)
    if choice:
        scenario_id, why = choice
        offers.append(NextCall(
            "library", scenario_id, persona.id, why, scenario_id not in choices.played_ids,
        ))
    return offers


def _library_choice(
    played: Candidate, choices: Choices
) -> tuple[str, Recommendation | None] | None:
    """The suggestion to offer next, preferring one not yet played."""
    others = [pick for pick in choices.picks if pick != played.id]
    fresh = [pick for pick in others if pick not in choices.played_ids]
    if fresh or others:
        pick = (fresh or others)[0]
        return pick, choices.picks[pick]

    def same_kind(c: Candidate) -> bool:
        return c.id != played.id and not c.reverse and c.category == played.category

    same = next((c for c in choices.candidates
                 if played.category and same_kind(c) and c.id not in choices.played_ids), None)
    return (same.id, None) if same else None


def next_for_subject(
    subject: str,
    played: Candidate,
    persona: Partner,
    candidates: list[Candidate],
    partners: list[Partner],
) -> list[NextCall]:
    """`next_calls` over this subject's own profile and history."""
    return next_calls(played, persona, Choices(
        candidates, partners,
        for_subject(subject, candidates), library.played_scenario_ids(subject),
    ))


def for_subject(subject: str, candidates: list[Candidate]) -> dict[str, Recommendation]:
    """`recommend` over this subject's own focus selection and training history."""
    with session_scope() as db:
        chosen = focus.selection(db, subject)
    return recommend(
        candidates, chosen.categories, chosen.keys, library.played_scenario_ids(subject)
    )
