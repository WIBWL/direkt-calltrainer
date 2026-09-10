"""Scenario suggestions from what a User said about their work (F-62).

Covers:
  F-62      call types and focus goals steer the suggestions, voice goals do not
  ADR 0076  a suggestion names its reason and claims no measurement
  ADR 0072  a suggested Scenario keeps its own origin: the suggestions are a
            view over the cards, not a group that takes them out of theirs

The scoring is a pure function over plain values; one test runs the listing.
"""
import httpx
import pytest

from backend.recommendations import (
    MAX_RECOMMENDATIONS,
    Candidate,
    Recommendation,
    recommend,
)


def _library(*categories: str | None) -> list[Candidate]:
    return [Candidate(f"s{i}", category, reverse=False) for i, category in enumerate(categories)]


def test_a_call_type_the_user_takes_is_suggested() -> None:
    """The kind of call the User takes is the strongest signal."""
    picks = recommend(_library("pricing", "operations"), ["pricing"], [], set())

    assert picks == {"s0": Recommendation(call_type=True, goals=())}


def test_a_goal_suggests_the_context_that_exercises_it() -> None:
    """Objection handling is practised where objections come up."""
    picks = recommend(_library("closing", "operations"), [], ["objection_handling"], set())

    assert picks == {"s0": Recommendation(call_type=False, goals=("objection_handling",))}


def test_voice_goals_steer_nothing() -> None:
    """Every Scenario trains the voice, so a voice goal cannot pick one."""
    assert recommend(_library("pricing", "closing"), [], ["pace", "intonation"], set()) == {}


def test_nothing_said_suggests_nothing() -> None:
    """No basis, no suggestion -- rather than an invented one."""
    assert recommend(_library("pricing"), [], [], set()) == {}


def test_a_reverse_or_an_uncategorised_scenario_is_never_suggested() -> None:
    """One replays a particular call, the other has no context to match."""
    candidates = [Candidate("rev", "pricing", reverse=True), Candidate("none", None, False)]

    assert recommend(candidates, ["pricing"], [], set()) == {}


def test_the_call_type_outweighs_one_goal() -> None:
    """2 for the kind of call the User takes, 1 per goal."""
    picks = recommend(_library("closing", "pricing"), ["pricing"], ["closing"], set())

    assert list(picks) == ["s1", "s0"]


def test_an_unplayed_scenario_wins_a_tie() -> None:
    """Otherwise the same suggestion would come back after every call."""
    picks = recommend(_library("pricing", "pricing"), ["pricing"], [], {"s0"})

    assert list(picks) == ["s1", "s0"]


def test_there_are_at_most_a_rowful() -> None:
    """One grid row, in front of the "show all" tile."""
    picks = recommend(_library(*["pricing"] * 9), ["pricing"], [], set())

    assert len(picks) == MAX_RECOMMENDATIONS


@pytest.mark.usefixtures("seeded_database")
async def test_the_listing_marks_suggestions_and_keeps_their_origin(
    api_client: httpx.AsyncClient,
) -> None:
    """The seeded library has three pricing Scenarios, all built in."""
    await api_client.put("/api/focus", json={"goals": [], "categories": ["pricing"]})

    cards = (await api_client.get("/api/scenarios")).json()
    suggested = [card for card in cards if card["recommendation"]]

    assert len(suggested) == 3
    assert all(card["category"] == "pricing" for card in suggested)
    assert all(card["origin"] == "builtin" for card in suggested)
    assert suggested[0]["recommendation"] == {"call_type": True, "goals": []}
