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


def for_subject(subject: str, candidates: list[Candidate]) -> dict[str, Recommendation]:
    """`recommend` over this subject's own focus selection and training history."""
    with session_scope() as db:
        chosen = focus.selection(db, subject)
    return recommend(
        candidates, chosen.categories, chosen.keys, library.played_scenario_ids(subject)
    )
