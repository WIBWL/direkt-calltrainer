"""Which Scenarios to suggest first, from what a User said about their work (F-62).

Rule-based; every suggestion carries its reason. Suggesting a Scenario claims
nothing about how the User does at a goal (ADR 0076).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from backend import focus, library
from backend.db.seed_data import FOCUS_GOALS
from backend.db.session import session_scope

# One row of the grid in front of the "show all" tile.
MAX_RECOMMENDATIONS = 5

# The call context that exercises a focus goal (`practised_in` in
# `seed_data.FOCUS_GOALS`). Voice goals and `opening` name none on purpose:
# every call trains the voice and has an opening, so they cannot steer.
GOAL_CATEGORIES: dict[str, tuple[str, ...]] = {
    goal["id"]: tuple(goal["practised_in"]) for goal in FOCUS_GOALS if goal.get("practised_in")
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

    Call type scores 2, each exercised goal 1; ties go to unplayed, then listing
    order. Reverses and uncategorised Scenarios are never suggested.
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
    played_ids = library.played_scenario_ids(subject)
    return next_calls(played, persona, Choices(
        candidates, partners,
        for_subject(subject, candidates, played_ids), played_ids,
    ))


def for_subject(
    subject: str, candidates: list[Candidate], played_ids: set[str] | None = None
) -> dict[str, Recommendation]:
    """`recommend` over this subject's own focus selection and training history.

    `played_ids` is for a caller that already read the history: `next_for_subject`
    needs it twice, and asked the database for it twice until it was passed in.
    """
    with session_scope() as db:
        chosen = focus.selection(db, subject)
    if played_ids is None:
        played_ids = library.played_scenario_ids(subject)
    return recommend(candidates, chosen.categories, chosen.keys, played_ids)
