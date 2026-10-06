"""Focus goals: the five-goal limit, "no focus" as an answer, untouched by deletion (F-62, ADR 0076)."""

# pylint: disable=duplicate-code  # each module carries its own fixture Turns on purpose

import httpx
import pytest
from sqlalchemy.orm import Session as DbSession

from shared.db.models import (
    FOCUS_EVIDENCE,
    FOCUS_GROUPS,
    SCENARIO_CATEGORIES,
    TRAINING_ROLES,
    FocusGoal,
    FocusSelection,
    FocusSelectionGoal,
    Persona,
    Scenario,
)
from shared.db.seed_data import FOCUS_GOALS as SEEDED_GOALS
from shared.turn import Turn as LiveTurn
from backend import deletion, focus
from backend.tests.conftest import TEST_AUTH, persist

# Needs the shipped catalogue; an empty one would make every test vacuous.
pytestmark = pytest.mark.usefixtures("seeded_database")

TURNS = [
    LiveTurn(seq=1, persona_text="Brandt hier.", persona_offset_ms=0, persona_end_ms=1500),
    LiveTurn(seq=2,
             user_text="Guten Tag!", user_offset_ms=1800, user_end_ms=2700,
             user_speech_ms=900, user_phonation_ms=700,
             persona_text="Zu teuer.", persona_offset_ms=3000, persona_end_ms=4100),
]


def test_the_catalogue_is_seeded(db_session: DbSession) -> None:
    rows = db_session.query(FocusGoal).all()

    assert len(rows) == len(SEEDED_GOALS)
    assert len({row.key for row in rows}) == len(rows)
    assert len({row.position for row in rows}) == len(rows)


def test_every_goal_declares_a_group_and_an_evidence_kind(db_session: DbSession) -> None:
    for row in db_session.query(FocusGoal).all():
        assert row.group_key in FOCUS_GROUPS, row.key
        assert row.evidence in FOCUS_EVIDENCE, row.key


def test_seeding_twice_changes_nothing(db_session: DbSession) -> None:
    # Imported here for the same reason conftest does: no environment at
    # collection time.
    from backend.db.provision import seed  # pylint: disable=import-outside-toplevel

    before = db_session.query(FocusGoal).count()
    seed(db_session)
    db_session.commit()

    assert db_session.query(FocusGoal).count() == before


async def test_the_catalogue_is_served_with_the_selection(
    api_client: httpx.AsyncClient,
) -> None:
    body = (await api_client.get("/api/focus")).json()

    assert body["max_goals"] == focus.MAX_GOALS
    assert len(body["goals"]) == len(SEEDED_GOALS)
    assert {g["key"] for g in body["groups"]} == set(FOCUS_GROUPS)
    # `evidence` stays off the wire (ADR 0076).
    first = body["goals"][0]
    assert set(first) == {"key", "title", "caption", "info", "group"}


async def test_a_retired_goal_is_no_longer_offered(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    db_session.query(FocusGoal).filter_by(key="empathy").update({"active": False})
    db_session.commit()

    body = (await api_client.get("/api/focus")).json()

    assert "empathy" not in {g["key"] for g in body["goals"]}
    assert (await api_client.put("/api/focus", json={"goals": ["empathy"]})).status_code == 400


async def test_a_new_account_is_asked(api_client: httpx.AsyncClient) -> None:
    body = (await api_client.get("/api/focus")).json()

    assert body["decided"] is False
    assert body["decision_required"] is True
    assert body["selected"] == []


async def test_a_selection_is_stored_and_read_back(api_client: httpx.AsyncClient) -> None:
    written = (await api_client.put(
        "/api/focus", json={"goals": ["pace", "talk_share"]}
    )).json()
    read = (await api_client.get("/api/focus")).json()

    assert written["decided"] is True
    assert set(written["selected"]) == {"pace", "talk_share"}
    assert read["selected"] == written["selected"]
    assert read["decision_required"] is False


async def test_continuing_without_a_focus_is_a_decision(
    api_client: httpx.AsyncClient,
) -> None:
    body = (await api_client.put("/api/focus", json={"goals": []})).json()

    assert body["decided"] is True
    assert body["decision_required"] is False
    assert body["selected"] == []


async def test_the_selection_is_returned_in_catalogue_order(
    api_client: httpx.AsyncClient,
) -> None:
    body = (await api_client.put(
        "/api/focus", json={"goals": ["closing", "pace", "empathy"]}
    )).json()

    assert body["selected"] == ["pace", "closing", "empathy"]


async def test_the_backend_refuses_a_sixth_goal(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    six = [g["id"] for g in SEEDED_GOALS[:6]]

    response = await api_client.put("/api/focus", json={"goals": six})

    assert response.status_code == 400
    assert db_session.query(FocusSelection).count() == 0


async def test_the_limit_is_exactly_five(api_client: httpx.AsyncClient) -> None:
    five = [g["id"] for g in SEEDED_GOALS[:5]]

    assert focus.MAX_GOALS == 5
    assert (await api_client.put("/api/focus", json={"goals": five})).status_code == 200


async def test_a_repeated_goal_costs_one_slot(api_client: httpx.AsyncClient) -> None:
    six_entries = [g["id"] for g in SEEDED_GOALS[:5]] + [SEEDED_GOALS[0]["id"]]

    body = (await api_client.put("/api/focus", json={"goals": six_entries})).json()

    assert len(body["selected"]) == 5


async def test_an_unknown_goal_is_refused(api_client: httpx.AsyncClient) -> None:
    response = await api_client.put(
        "/api/focus", json={"goals": ["pace", "no-such-goal"]}
    )

    assert response.status_code == 400


async def test_changing_the_selection_replaces_it(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    await api_client.put("/api/focus", json={"goals": ["pace", "intonation"]})
    body = (await api_client.put("/api/focus", json={"goals": ["empathy"]})).json()

    assert body["selected"] == ["empathy"]
    assert db_session.query(FocusSelectionGoal).count() == 1
    assert db_session.query(FocusSelection).count() == 1


async def test_changing_the_selection_keeps_when_it_was_first_decided(
    api_client: httpx.AsyncClient,
) -> None:
    first = (await api_client.put("/api/focus", json={"goals": ["pace"]})).json()
    second = (await api_client.put("/api/focus", json={"goals": ["closing"]})).json()

    assert second["decided_at"] == first["decided_at"]


def test_a_selection_survives_a_goal_being_retired(db_session: DbSession) -> None:
    focus.set_selection(db_session, TEST_AUTH.sub, ["pace", "empathy"])
    db_session.commit()

    db_session.query(FocusGoal).filter_by(key="empathy").update({"active": False})
    db_session.commit()

    assert focus.selection(db_session, TEST_AUTH.sub).keys == ("pace", "empathy")


async def test_a_retired_goal_leaves_the_served_selection(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    await api_client.put("/api/focus", json={"goals": ["pace", "empathy"]})
    db_session.query(FocusGoal).filter_by(key="empathy").update({"active": False})
    db_session.commit()

    body = (await api_client.get("/api/focus")).json()

    assert body["selected"] == ["pace"]
    assert body["decided"] is True


async def test_one_subject_never_sees_another_subjects_focus(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    focus.set_selection(db_session, "somebody-else", ["pace", "intonation"])
    db_session.commit()

    body = (await api_client.get("/api/focus")).json()

    assert body["decided"] is False
    assert body["selected"] == []


def test_deleting_the_trainings_leaves_the_focus_alone(db_session: DbSession) -> None:
    # Against the seeded data; adding `reference_data` would insert the catalogue twice.
    persona = db_session.query(Persona).filter(Persona.key.isnot(None)).first()
    scenario = db_session.query(Scenario).filter(Scenario.key.isnot(None)).first()
    persist(turns=TURNS, persona_key=persona.key, scenario_key=scenario.key)
    focus.set_selection(db_session, TEST_AUTH.sub, ["pace"])
    db_session.commit()

    deletion.delete_subject_sessions(db_session, TEST_AUTH.sub)
    db_session.commit()

    assert focus.selection(db_session, TEST_AUTH.sub).keys == ("pace",)


async def test_role_and_call_types_are_stored_and_read_back(
    api_client: httpx.AsyncClient,
) -> None:
    await api_client.put("/api/focus", json={
        "goals": ["pace"], "role": "sales", "categories": ["closing", "pricing"],
    })
    read = (await api_client.get("/api/focus")).json()

    assert read["role"] == "sales"
    # Vocabulary order, not the order they were sent in.
    assert read["categories"] == ["pricing", "closing"]


async def test_leaving_them_out_clears_them(api_client: httpx.AsyncClient) -> None:
    await api_client.put("/api/focus", json={"goals": [], "role": "support",
                                             "categories": ["operations"]})
    body = (await api_client.put("/api/focus", json={"goals": []})).json()

    assert body["role"] is None
    assert body["categories"] == []


@pytest.mark.parametrize("choice", [{"role": "pilot"}, {"categories": ["smalltalk"]}])
async def test_an_unknown_role_or_call_type_is_refused(
    api_client: httpx.AsyncClient, choice: dict,
) -> None:
    response = await api_client.put("/api/focus", json={"goals": [], **choice})

    assert response.status_code == 400


def test_every_role_preselects_known_call_types() -> None:
    assert [role["key"] for role in focus.roles()] == list(TRAINING_ROLES)
    for role in focus.roles():
        assert set(role["categories"]) <= set(SCENARIO_CATEGORIES)
