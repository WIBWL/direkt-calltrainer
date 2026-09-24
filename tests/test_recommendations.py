"""Scenario suggestions from what a User said about their work.

Covers F-62 (call types and focus goals steer, voice goals do not), ADR 0076 (names its reason,
claims no measurement), ADR 0072 (a view, cards keep their origin), F-64/ADR 0087 (what to play
next, without a model or stored Session). Scoring is pure; one test runs the listing."""
from pathlib import Path

import httpx
import pytest

from backend.db.seed_data import FOCUS_GOALS
from backend.feedback.generator import _NEVER_ASSIGNED
from backend.recommendations import (
    GOAL_CATEGORIES,
    MAX_RECOMMENDATIONS,
    Candidate,
    Choices,
    NextCall,
    Partner,
    Recommendation,
    next_calls,
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


# --- What to play next (F-64) -------------------------------------------------------

_GERMAN, _ENGLISH = Partner("thomas", "de"), Partner("samantha", "en")


def test_the_same_scenario_is_offered_in_the_other_language() -> None:
    """With one Persona per language, another partner is another language."""
    offers = next_calls(Candidate("s0", "pricing", False), _GERMAN,
                        Choices([], [_GERMAN, _ENGLISH], {}, set()))

    assert offers == [NextCall("language", "s0", "samantha")]


def test_a_reverse_is_not_offered_in_another_language() -> None:
    """Its briefing is German prose (ADR 0070)."""
    offers = next_calls(Candidate("rev", "pricing", True), _GERMAN,
                        Choices([], [_GERMAN, _ENGLISH], {}, set()))

    assert not offers


def test_the_best_unplayed_suggestion_is_offered_next() -> None:
    """Not the Scenario just played, and one not yet played before one that was."""
    picks = {"s0": Recommendation(True, ()), "s1": Recommendation(True, ()),
             "s2": Recommendation(True, ())}
    offers = next_calls(Candidate("s0", "pricing", False), _GERMAN,
                        Choices([], [_GERMAN], picks, {"s0", "s1"}))

    assert offers == [NextCall("library", "s2", "thomas", Recommendation(True, ()), True)]


def test_without_a_profile_the_same_category_is_offered() -> None:
    """Nothing said about the work: an unplayed Scenario of the same kind of call."""
    library = [Candidate("s0", "pricing", False), Candidate("s1", "closing", False),
               Candidate("s2", "pricing", False)]
    offers = next_calls(library[0], _GERMAN, Choices(library, [_GERMAN], {}, set()))

    assert offers == [NextCall("library", "s2", "thomas", None, True)]


@pytest.mark.usefixtures("seeded_database")
async def test_the_route_offers_the_other_language_and_another_scenario(
    api_client: httpx.AsyncClient,
) -> None:
    """The seeded library: one German and one English Persona, no profile."""
    scenarios = (await api_client.get("/api/scenarios")).json()
    personas = (await api_client.get("/api/personas")).json()
    german = next(p for p in personas if p["language"] == "Deutsch")
    english = next(p for p in personas if p["language"] == "Englisch")

    offers = (await api_client.get(
        f"/api/scenarios/{scenarios[0]['id']}/next", params={"persona": german["id"]}
    )).json()

    assert [offer["kind"] for offer in offers] == ["language", "library"]
    assert offers[0]["persona_id"] == english["id"]
    assert offers[0]["scenario_id"] == scenarios[0]["id"]
    assert offers[1]["scenario_id"] != scenarios[0]["id"]


@pytest.mark.usefixtures("seeded_database")
async def test_an_unknown_scenario_has_no_next(api_client: httpx.AsyncClient) -> None:
    """A 404, like every other route for a Scenario the caller cannot see."""
    response = await api_client.get(
        "/api/scenarios/00000000-0000-0000-0000-000000000000/next", params={"persona": "x"}
    )

    assert response.status_code == 404


PRACTICE_ROUTES_TS = (
    Path(__file__).resolve().parent.parent /
    "frontend" / "src" / "utils" / "practiceRoutes.ts"
)


def _practice_category() -> dict[str, str | None]:
    """The progress view's goal -> call type table, as written in the source.

    Read out of the source rather than executed, the way `test_metrics.py`
    reads the metric catalogue: there is no Node in the pytest run.
    """
    text = PRACTICE_ROUTES_TS.read_text(encoding="utf-8")
    body = text.split("export const PRACTICE_CATEGORY", 1)[1].split("= {", 1)[1]
    body = body.split("\n};", 1)[0]
    table: dict[str, str | None] = {}
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        key, _, value = line.partition(":")
        value = value.strip().rstrip(",").strip()
        table[key.strip()] = None if value == "null" else value.strip('"')
    return table


def test_the_practice_offer_uses_the_first_kind_of_call_on_the_goal_s_row() -> None:
    """`practiceRoutes.ts` must pick the *first* `practised_in` category of each goal row.

    The two had drifted, sending one goal to different call types on two screens.
    """
    practice = _practice_category()
    assert practice, "PRACTICE_CATEGORY parsed as empty; has its shape changed?"

    for goal in FOCUS_GOALS:
        if goal["group"] == "habit":
            continue
        practised_in = goal.get("practised_in") or ()
        expected = practised_in[0] if practised_in else None
        assert practice.get(goal["id"], "missing") == expected, (
            f"{goal['id']} is practised in {practised_in or 'no kind of call'} on its "
            f"row, but PRACTICE_CATEGORY says {practice.get(goal['id'], 'nothing')}"
        )

    assert set(GOAL_CATEGORIES) == {g["id"] for g in FOCUS_GOALS if g.get("practised_in")}


def test_every_goal_the_wrap_up_can_name_has_somewhere_to_practise_it() -> None:
    """Every catalogue goal (bar the two habit goals, never named in a wrap-up) needs a practice entry.

    A missing goal yields no suggestion by design, so adding one forces a decision; this check
    makes sure somebody notices instead of the block silently going empty.
    """
    practice = _practice_category()
    assignable = {goal["id"] for goal in FOCUS_GOALS} - set(_NEVER_ASSIGNED)

    missing = assignable - set(practice)
    assert not missing, (
        f"{sorted(missing)} can be named as an improvement but has no entry in "
        f"PRACTICE_CATEGORY, so the practice block stays empty for it"
    )
