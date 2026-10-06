"""`GET /api/sessions`: ownership in the query, total order, what is left out (F-13, F-48, ADR 0064)."""

# pylint: disable=duplicate-code  # each module carries its own fixture Turns on purpose

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy.orm import Session as DbSession

from shared.db.models import AnalysisJob, Feedback, FeedbackPoint, FocusGoal, Session
from shared.turn import Turn
from shared.tests.fixtures import METRIC_KEY
from backend import auth
from backend.app import app
from backend.tests.conftest import persist

pytestmark = pytest.mark.usefixtures("reference_data")

# Distinct instants, deliberately not in the order they are written: a listing
# that returned insertion order would pass a test whose timestamps ascend.
JUNE = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)
JULY = datetime(2026, 7, 1, 9, 0, tzinfo=UTC)
AUGUST = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)

MEASURED_TURNS = [
    Turn(seq=1, persona_text="Brandt hier.", persona_offset_ms=0, persona_end_ms=1500),
    Turn(seq=2,
         user_text="Guten Tag!", user_offset_ms=1800, user_end_ms=2700,
         user_speech_ms=900, user_phonation_ms=700,
         persona_text="Zu teuer.", persona_offset_ms=3000, persona_end_ms=4100),
]


async def test_history_is_empty_before_the_first_call(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.get("/api/sessions")

    assert response.status_code == 200
    assert response.json() == {"total": 0, "limit": 20, "offset": 0, "sessions": []}


async def test_history_holds_only_the_callers_own_sessions(
    api_client: httpx.AsyncClient,
) -> None:
    mine = persist()
    persist(subject="somebody-else")
    persist(subject="a-third-party")

    body = (await api_client.get("/api/sessions")).json()

    assert body["total"] == 1
    assert [s["session_id"] for s in body["sessions"]] == [str(mine)]


async def test_history_returns_the_newest_session_first(
    api_client: httpx.AsyncClient,
) -> None:
    june = persist(started_at=JUNE)
    august = persist(started_at=AUGUST)
    july = persist(started_at=JULY)

    body = (await api_client.get("/api/sessions")).json()

    assert [s["session_id"] for s in body["sessions"]] == [
        str(august), str(july), str(june),
    ]


async def test_sessions_sharing_a_timestamp_still_have_one_order(
    api_client: httpx.AsyncClient,
) -> None:
    written = {str(persist(started_at=JULY)) for _ in range(5)}

    paged: list[str] = []
    for offset in range(len(written)):
        page = (
            await api_client.get("/api/sessions", params={"limit": 1, "offset": offset})
        ).json()["sessions"]
        paged += [s["session_id"] for s in page]

    assert len(paged) == len(written), "a page was short despite rows remaining"
    assert len(set(paged)) == len(paged), "a Session appeared on two pages"
    assert set(paged) == written, "a Session was never paged through"


async def test_pagination_slices_without_losing_the_total(
    api_client: httpx.AsyncClient,
) -> None:
    for month in (JUNE, JULY, AUGUST):
        persist(started_at=month)

    body = (await api_client.get("/api/sessions", params={"limit": 2})).json()

    assert body["total"] == 3
    assert body["limit"] == 2
    assert len(body["sessions"]) == 2

    second = (
        await api_client.get("/api/sessions", params={"limit": 2, "offset": 2})
    ).json()
    assert second["total"] == 3
    assert len(second["sessions"]) == 1


async def test_total_counts_only_the_caller(api_client: httpx.AsyncClient) -> None:
    persist()
    persist(subject="somebody-else")

    body = (await api_client.get("/api/sessions")).json()

    assert body["total"] == 1


@pytest.mark.parametrize(
    "params",
    [{"limit": 0}, {"limit": 101}, {"limit": -1}, {"offset": -1}],
    ids=["limit too small", "limit over the cap", "negative limit", "negative offset"],
)
async def test_page_bounds_are_enforced(
    api_client: httpx.AsyncClient, params: dict
) -> None:
    response = await api_client.get("/api/sessions", params=params)

    assert response.status_code == 422


async def test_a_row_carries_what_the_history_list_shows(
    api_client: httpx.AsyncClient,
) -> None:
    persist(turns=MEASURED_TURNS, started_at=JULY)

    body = (await api_client.get("/api/sessions")).json()

    row = body["sessions"][0]
    assert set(row) == {
        "session_id", "persona", "scenario", "status", "has_feedback",
        "feedback_status", "started_at", "ended_at", "measurements",
        # Which side the User was on (ADR 0070) -- two rows on the same
        # Scenario are otherwise indistinguishable.
        "reverse",
        # The kind of call, so the progress view can read a course over one kind.
        "category",
        # Tagged points with their text (ADR 0064); the wrap-up itself stays on the detail route.
        "feedback_goals",
        # Beside `measurements`, which readers assume holds one entry per metric.
        "segments",
    }
    assert row["persona"] == "Thomas Brandt"
    assert row["scenario"] == "Kündigungsabsicht"
    assert row["status"] == "completed"
    assert row["started_at"] == JULY.isoformat()


async def test_an_aborted_session_is_listed_as_aborted(
    api_client: httpx.AsyncClient,
) -> None:
    persist(reason="error")

    body = (await api_client.get("/api/sessions")).json()

    assert body["total"] == 1
    assert body["sessions"][0]["status"] == "aborted"


async def test_measurements_travel_with_each_session(
    api_client: httpx.AsyncClient,
) -> None:
    persist(turns=MEASURED_TURNS, started_at=JUNE)
    persist(turns=MEASURED_TURNS, started_at=JULY)

    body = (await api_client.get("/api/sessions")).json()

    for row in body["sessions"]:
        keys = [m["key"] for m in row["measurements"]]
        assert keys == [METRIC_KEY]
        assert keys == sorted(set(keys)), "one Session must not carry a metric twice"
        assert row["measurements"][0]["value"] > 0


async def test_the_loudness_curve_stays_out_of_the_listing(
    api_client: httpx.AsyncClient,
) -> None:
    persist(turns=MEASURED_TURNS)

    body = (await api_client.get("/api/sessions")).json()

    measurement = body["sessions"][0]["measurements"][0]
    assert set(measurement) == {"key", "name", "unit", "value", "aspect"}
    assert "detail" not in measurement


async def test_the_listing_says_whether_a_wrap_up_exists_but_not_what_it_says(
    api_client: httpx.AsyncClient,
) -> None:
    persist(turns=MEASURED_TURNS)

    row = (await api_client.get("/api/sessions")).json()["sessions"][0]

    assert row["has_feedback"] is False
    assert "feedback" not in row
    assert "summary" not in row
    assert "phase_language" not in row
    assert "turns" not in row


async def test_the_wrap_up_state_does_not_overload_status(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    persist(turns=MEASURED_TURNS, reason="error")
    _write_feedback(db_session)

    row = (await api_client.get("/api/sessions")).json()["sessions"][0]

    assert row["status"] == "aborted"          # the call
    assert row["feedback_status"] == "queued"  # its wrap-up job
    assert row["has_feedback"] is True


async def test_a_stored_wrap_up_is_announced_in_the_listing(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    persist(turns=MEASURED_TURNS)
    _write_feedback(db_session)

    row = (await api_client.get("/api/sessions")).json()["sessions"][0]

    assert row["has_feedback"] is True


async def test_a_wrap_up_that_never_arrived_is_not_announced_as_pending(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    persist(turns=MEASURED_TURNS)
    job = db_session.query(AnalysisJob).one()
    job.status = "failed"
    db_session.commit()

    row = (await api_client.get("/api/sessions")).json()["sessions"][0]

    assert row["has_feedback"] is False
    assert row["feedback_status"] == "failed"


async def test_a_tagged_point_travels_with_its_goal_and_its_text(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    persist(turns=MEASURED_TURNS)
    _write_feedback(db_session, points=[("improvement", "closing", "Kein Termin vereinbart.")])

    row = (await api_client.get("/api/sessions")).json()["sessions"][0]

    assert row["feedback_goals"] == [
        {"kind": "improvement", "goal": "closing", "text": "Kein Termin vereinbart."}
    ]


async def test_an_untagged_point_stays_out_of_the_listing(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    persist(turns=MEASURED_TURNS)
    _write_feedback(
        db_session,
        points=[("strength", "pace", "Ruhiges Tempo."), ("improvement", None, "Etwas leise.")],
    )

    row = (await api_client.get("/api/sessions")).json()["sessions"][0]

    assert [tag["goal"] for tag in row["feedback_goals"]] == ["pace"]
    assert "Etwas leise." not in str(row)


async def test_the_wrap_up_itself_still_stays_on_the_detail_route(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    persist(turns=MEASURED_TURNS)
    _write_feedback(db_session, points=[("strength", "pace", "Ruhiges Tempo.")])

    row = (await api_client.get("/api/sessions")).json()["sessions"][0]

    assert "Zusammenfassung." not in str(row)
    assert "summary" not in row


def _write_feedback(
    db: DbSession, points: list[tuple[str, str | None, str]] | None = None
) -> None:
    """`points` are (kind, focus-goal key or None, text)."""
    session_id = db.query(Session).one().session_id
    feedback = Feedback(
        session_id=session_id,
        summary="Zusammenfassung.",
        created_at=datetime.now(UTC),
    )
    for position, (kind, goal_key, text) in enumerate(points or []):
        goal = db.query(FocusGoal).filter_by(key=goal_key).one() if goal_key else None
        feedback.points.append(
            FeedbackPoint(position=position, kind=kind, text=text, focus_goal=goal)
        )
    db.add(feedback)
    db.commit()


async def test_the_history_needs_a_token(api_client: httpx.AsyncClient) -> None:
    persist()
    app.dependency_overrides.pop(auth.require_user, None)  # drop conftest's override

    assert (await api_client.get("/api/sessions")).status_code == 401


async def test_a_session_from_the_history_opens_on_the_detail_route(
    api_client: httpx.AsyncClient,
) -> None:
    persist(turns=MEASURED_TURNS, extern_id=uuid.uuid4())

    listed = (await api_client.get("/api/sessions")).json()["sessions"][0]
    detail = await api_client.get(f"/api/sessions/{listed['session_id']}")

    assert detail.status_code == 200
    assert detail.json()["session_id"] == listed["session_id"]
