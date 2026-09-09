"""The training focus a User picks, and the catalogue behind it (F-61, ADR 0074).

Three properties carry this file.

The limit is the feature: a focus that covers everything is not a focus, so the
sixth goal has to be refused by the *backend* and not merely greyed out in the
interface — a limit only the client enforces is not a limit.

"No focus" and "not asked yet" are different states. The first-run dialog opens
on exactly one of them, and getting that wrong means either asking a user who
already answered, every time they load the app, or never asking at all.

And a selection is a setting, not training data: deleting your trainings, by
whatever route, must leave the goals you picked alone. That one is asserted
here rather than in the deletion tests because it is a property of this feature
— nothing in `deletion.py` mentions focus, and this test is what would notice
if something did.
"""
import httpx
import pytest
from sqlalchemy.orm import Session as DbSession

from backend import deletion, focus
from backend.db.models import (
    FOCUS_EVIDENCE,
    FOCUS_GROUPS,
    FocusGoal,
    FocusSelection,
    FocusSelectionGoal,
)
from backend.db.seed_data import FOCUS_GOALS as SEEDED_GOALS
from backend.session.models import Turn as LiveTurn
from tests.conftest import TEST_AUTH, persist

# Every test here needs the shipped catalogue in the database: without it there
# is nothing to select, and a test that passed on an empty catalogue would be
# asserting nothing.
pytestmark = pytest.mark.usefixtures("seeded_database")

TURNS = [
    LiveTurn(seq=1, persona_text="Brandt hier.", persona_offset_ms=0, persona_end_ms=1500),
    LiveTurn(seq=2,
             user_text="Guten Tag!", user_offset_ms=1800, user_end_ms=2700,
             user_speech_ms=900, user_phonation_ms=700,
             persona_text="Zu teuer.", persona_offset_ms=3000, persona_end_ms=4100),
]


# --- The catalogue -----------------------------------------------------------


def test_the_catalogue_is_seeded(db_session: DbSession) -> None:
    """Every entry of seed_data.py reaches the table, keys and positions
    unique. A duplicate position would make the display order depend on the
    database's row order, which is not an order at all."""
    rows = db_session.query(FocusGoal).all()

    assert len(rows) == len(SEEDED_GOALS)
    assert len({row.key for row in rows}) == len(rows)
    assert len({row.position for row in rows}) == len(rows)


def test_every_goal_declares_a_group_and_an_evidence_kind(db_session: DbSession) -> None:
    """Both are closed vocabularies with a CHECK behind them. The group decides
    the heading a card sits under; `evidence` records how far a goal can be
    derived from a recording today and stays internal, which is why the payload
    test below asserts it is *not* on the wire (ADR 0074)."""
    for row in db_session.query(FocusGoal).all():
        assert row.group_key in FOCUS_GROUPS, row.key
        assert row.evidence in FOCUS_EVIDENCE, row.key


def test_seeding_twice_changes_nothing(db_session: DbSession) -> None:
    """The app seeds on every start (provision.py), so a second run must not
    duplicate the catalogue or reset anybody's selection."""
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
    """One route, both halves. The dialog needs the catalogue *and* whether the
    question was answered, and two requests would let it render half a state."""
    body = (await api_client.get("/api/focus")).json()

    assert body["max_goals"] == focus.MAX_GOALS
    assert len(body["goals"]) == len(SEEDED_GOALS)
    assert {g["key"] for g in body["groups"]} == set(FOCUS_GROUPS)
    # Every goal carries the text the card shows and nothing more. `evidence` is
    # planning information for the analysis work and stays off the wire, so a
    # user is never asked to weigh up how far a goal is measurable (ADR 0074).
    first = body["goals"][0]
    assert set(first) == {"key", "title", "caption", "info", "group"}


async def test_a_retired_goal_is_no_longer_offered(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    """Deactivated, not deleted: selections reference the row. It leaves the
    catalogue the same way a retired Persona leaves the setup screen."""
    db_session.query(FocusGoal).filter_by(key="empathy").update({"active": False})
    db_session.commit()

    body = (await api_client.get("/api/focus")).json()

    assert "empathy" not in {g["key"] for g in body["goals"]}
    assert (await api_client.put("/api/focus", json={"goals": ["empathy"]})).status_code == 400


# --- Deciding ----------------------------------------------------------------


async def test_a_new_account_is_asked(api_client: httpx.AsyncClient) -> None:
    """No row, no decision — the dialog opens."""
    body = (await api_client.get("/api/focus")).json()

    assert body["decided"] is False
    assert body["decision_required"] is True
    assert body["selected"] == []


async def test_a_selection_is_stored_and_read_back(api_client: httpx.AsyncClient) -> None:
    """The ordinary case. The response of the write is the state that now
    holds, so the client never has to re-fetch to find out what it saved."""
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
    """"Ohne Fokus fortfahren" answers the question. Reading it as "not asked
    yet" would put the dialog in front of the user on every single start, which
    turns a free choice into something they have to keep fending off."""
    body = (await api_client.put("/api/focus", json={"goals": []})).json()

    assert body["decided"] is True
    assert body["decision_required"] is False
    assert body["selected"] == []


async def test_the_selection_is_returned_in_catalogue_order(
    api_client: httpx.AsyncClient,
) -> None:
    """Nothing about the selection is ranked, so it comes back in the order the
    catalogue has rather than in the order the boxes happened to be ticked —
    which would suggest a priority the user never expressed."""
    body = (await api_client.put(
        "/api/focus", json={"goals": ["closing", "pace", "empathy"]}
    )).json()

    assert body["selected"] == ["pace", "closing", "empathy"]


# --- The limit ---------------------------------------------------------------


async def test_the_backend_refuses_a_sixth_goal(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    """The limit is the feature, so it lives here and not only in the picker.
    Nothing is stored — storing the first five would file a focus the user did
    not pick and give them no way of noticing."""
    six = [g["id"] for g in SEEDED_GOALS[:6]]

    response = await api_client.put("/api/focus", json={"goals": six})

    assert response.status_code == 400
    assert db_session.query(FocusSelection).count() == 0


async def test_the_limit_is_exactly_five(api_client: httpx.AsyncClient) -> None:
    """The number itself, pinned on the boundary. Five is a decision, and
    changing it should fail a test rather than slip through as an edit."""
    five = [g["id"] for g in SEEDED_GOALS[:5]]

    assert focus.MAX_GOALS == 5
    assert (await api_client.put("/api/focus", json={"goals": five})).status_code == 200


async def test_a_repeated_goal_costs_one_slot(api_client: httpx.AsyncClient) -> None:
    """Six entries, five goals: the same goal twice is one goal, not two. The
    unique constraint would otherwise reject the write outright."""
    six_entries = [g["id"] for g in SEEDED_GOALS[:5]] + [SEEDED_GOALS[0]["id"]]

    body = (await api_client.put("/api/focus", json={"goals": six_entries})).json()

    assert len(body["selected"]) == 5


async def test_an_unknown_goal_is_refused(api_client: httpx.AsyncClient) -> None:
    """A key the catalogue does not offer is a client bug. Dropping it silently
    would store four of the five goals the user thinks they picked."""
    response = await api_client.put(
        "/api/focus", json={"goals": ["pace", "no-such-goal"]}
    )

    assert response.status_code == 400


# --- Changing it -------------------------------------------------------------


async def test_changing_the_selection_replaces_it(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    """The body is the whole selection, so the previous goals go. Rows left
    behind would be invisible on screen and still count against the limit."""
    await api_client.put("/api/focus", json={"goals": ["pace", "loudness"]})
    body = (await api_client.put("/api/focus", json={"goals": ["empathy"]})).json()

    assert body["selected"] == ["empathy"]
    assert db_session.query(FocusSelectionGoal).count() == 1
    assert db_session.query(FocusSelection).count() == 1


async def test_changing_the_selection_keeps_when_it_was_first_decided(
    api_client: httpx.AsyncClient,
) -> None:
    """`decided_at` records that the question was answered, which a later
    change does not unmake."""
    first = (await api_client.put("/api/focus", json={"goals": ["pace"]})).json()
    second = (await api_client.put("/api/focus", json={"goals": ["closing"]})).json()

    assert second["decided_at"] == first["decided_at"]


def test_a_selection_survives_a_goal_being_retired(db_session: DbSession) -> None:
    """The row stays readable, which is the whole reason retirement is a flag
    and not a delete. The interface drops the card; the database keeps the fact."""
    focus.set_selection(db_session, TEST_AUTH.sub, ["pace", "empathy"])
    db_session.commit()

    db_session.query(FocusGoal).filter_by(key="empathy").update({"active": False})
    db_session.commit()

    assert focus.selection(db_session, TEST_AUTH.sub).keys == ("pace", "empathy")


# --- Scope and survival ------------------------------------------------------


async def test_one_subject_never_sees_another_subjects_focus(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    """The `sub` is part of the query, not a check on the result — there is no
    form of this request that is about somebody else (ADR 0031/0064)."""
    focus.set_selection(db_session, "somebody-else", ["pace", "loudness"])
    db_session.commit()

    body = (await api_client.get("/api/focus")).json()

    assert body["decided"] is False
    assert body["selected"] == []


def test_deleting_the_trainings_leaves_the_focus_alone(db_session: DbSession) -> None:
    """A focus is a setting, not training data: withdrawing consent deletes the
    Sessions (ADR 0066) and must not quietly reset what the user chose to work
    on. `retention_preference` is treated the same way."""
    persist(turns=TURNS)
    focus.set_selection(db_session, TEST_AUTH.sub, ["pace"])
    db_session.commit()

    deletion.delete_subject_sessions(db_session, TEST_AUTH.sub)
    db_session.commit()

    assert focus.selection(db_session, TEST_AUTH.sub).keys == ("pace",)
