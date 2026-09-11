"""The caller's own Session history: `GET /api/sessions` (F-13, F-48).

The read side ADR 0028 and ADR 0052 both named as the condition for revisiting
themselves. Two things are load-bearing here and neither is visible in a happy
path, so both get a test of their own: the listing is filtered by `subject_id`
rather than checked after the fact, and its order is total rather than merely
mostly-determined — a tie on `started_at` broken by nothing would let one row
appear on two pages or on none.

What the listing deliberately does *not* carry is checked too. `detail_json`
would drag the whole loudness curve of every Session into a list view, and the
wrap-up would give `status` a second meaning on the same resource (ADR 0057).
"""
import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy.orm import Session as DbSession

from backend import auth
from backend.app import app
from backend.db.models import AnalysisJob, Feedback, Session
from backend.session.models import Turn
from tests.conftest import METRIC_KEY, persist

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
    """A new account has no history, which is an empty list and not a 404 —
    the collection exists, it just has nothing in it yet."""
    response = await api_client.get("/api/sessions")

    assert response.status_code == 200
    assert response.json() == {"total": 0, "limit": 20, "offset": 0, "sessions": []}


async def test_history_holds_only_the_callers_own_sessions(
    api_client: httpx.AsyncClient,
) -> None:
    """Ownership is the query, not a check applied to its result (ADR 0031).

    Someone else's Session is not filtered out of the response — it is never
    selected, which is why there is no route that could leak one.
    """
    mine = persist()
    persist(subject="somebody-else")
    persist(subject="a-third-party")

    body = (await api_client.get("/api/sessions")).json()

    assert body["total"] == 1
    assert [s["session_id"] for s in body["sessions"]] == [str(mine)]


async def test_history_returns_the_newest_session_first(
    api_client: httpx.AsyncClient,
) -> None:
    """The history reads as a reverse chronology, so the most recent training
    is the one the user lands on."""
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
    """`started_at` comes from the client's `session.activate`, so two Sessions
    can genuinely share one. Without the tiebreak Postgres may order them
    differently on each read, and a paginated client would see a row twice or
    not at all.

    Asserted as the property the tiebreak actually protects rather than as a
    stable byte-for-byte answer: paging one row at a time through Sessions that
    all share an instant has to yield each of them exactly once. Under a
    partial order the pages are free to overlap, and a row would go missing in
    exchange for one seen twice.
    """
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
    """`total` counts the caller's Sessions, not the page — the client cannot
    tell from a full page whether another one exists."""
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
    """The count runs on the filtered query. A total that included everyone
    would page through nothing and advertise pages that do not exist."""
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
    """The cap is what keeps one request from loading a heavy user's whole
    past; without it the trend view would simply ask for everything."""
    response = await api_client.get("/api/sessions", params=params)

    assert response.status_code == 422


async def test_a_row_carries_what_the_history_list_shows(
    api_client: httpx.AsyncClient,
) -> None:
    """The keys are the schema's own (ADR 0057), and `status` is
    `session.status` — completed or aborted — not the feedback status the
    detail route reports under that name."""
    persist(turns=MEASURED_TURNS, started_at=JULY)

    body = (await api_client.get("/api/sessions")).json()

    row = body["sessions"][0]
    assert set(row) == {
        "session_id", "persona", "scenario", "status", "has_feedback",
        "feedback_status", "started_at", "ended_at", "measurements",
        # Which side the User was on (ADR 0070) -- two rows on the same
        # Scenario are otherwise indistinguishable.
        "reverse",
    }
    assert row["persona"] == "Thomas Brandt"
    assert row["scenario"] == "Kündigungsabsicht"
    assert row["status"] == "completed"
    assert row["started_at"] == JULY.isoformat()


async def test_an_aborted_session_is_listed_as_aborted(
    api_client: httpx.AsyncClient,
) -> None:
    """A call the pipeline cut short (ADR 0016) still belongs in the history:
    it happened, and hiding it would make the count disagree with the user's
    memory of their own training."""
    persist(reason="error")

    body = (await api_client.get("/api/sessions")).json()

    assert body["total"] == 1
    assert body["sessions"][0]["status"] == "aborted"


async def test_measurements_travel_with_each_session(
    api_client: httpx.AsyncClient,
) -> None:
    """One point per Session per metric is what a trend over time is made of,
    and ADR 0051 already guarantees there is exactly one."""
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
    """`detail_json` is the per-Session course of a metric. Multiplied by a
    page of Sessions it dwarfs everything else in the payload, and no view
    across Sessions plots it — the detail route is where it belongs."""
    persist(turns=MEASURED_TURNS)

    body = (await api_client.get("/api/sessions")).json()

    measurement = body["sessions"][0]["measurements"][0]
    assert set(measurement) == {"key", "name", "unit", "value"}
    assert "detail" not in measurement


async def test_the_listing_says_whether_a_wrap_up_exists_but_not_what_it_says(
    api_client: httpx.AsyncClient,
) -> None:
    """A row carries the wrap-up's availability, never its text.

    Whether one exists decides what the row promises when clicked, so the list
    needs it. The narrative itself belongs to the detail route, and a page of
    summaries would dwarf everything else here for a view that shows none of
    them.
    """
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
    """`status` stays the Session's own outcome (ADR 0057). The wrap-up's state
    travels under its own name, or a reader would have to know which of the two
    routes it came from to know what it meant."""
    persist(turns=MEASURED_TURNS, reason="error")
    _write_feedback(db_session)

    row = (await api_client.get("/api/sessions")).json()["sessions"][0]

    assert row["status"] == "aborted"          # the call
    assert row["feedback_status"] == "queued"  # its wrap-up job
    assert row["has_feedback"] is True


async def test_a_stored_wrap_up_is_announced_in_the_listing(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    """The history's chip is drawn from this: a Session whose wrap-up was
    written is one the user can open and read."""
    persist(turns=MEASURED_TURNS)
    _write_feedback(db_session)

    row = (await api_client.get("/api/sessions")).json()["sessions"][0]

    assert row["has_feedback"] is True


async def test_a_wrap_up_that_never_arrived_is_not_announced_as_pending(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    """A job that failed will not produce anything later, and the row has to
    say so — telling the user it is still being generated is what the detail
    screen used to do wrongly for days-old Sessions."""
    persist(turns=MEASURED_TURNS)
    job = db_session.query(AnalysisJob).one()
    job.status = "failed"
    db_session.commit()

    row = (await api_client.get("/api/sessions")).json()["sessions"][0]

    assert row["has_feedback"] is False
    assert row["feedback_status"] == "failed"


def _write_feedback(db: DbSession) -> None:
    """Give the stored Session a wrap-up, the way the worker would."""
    session_id = db.query(Session).one().session_id
    db.add(
        Feedback(
            session_id=session_id,
            summary="Zusammenfassung.",
            created_at=datetime.now(UTC),
        )
    )
    db.commit()


async def test_the_history_needs_a_token(api_client: httpx.AsyncClient) -> None:
    """F-31/F-50/ADR 0009: without a caller there is no `sub` to filter by, so
    an unauthenticated listing has no defensible answer other than 401."""
    persist()
    app.dependency_overrides.pop(auth.require_user, None)  # drop conftest's override

    assert (await api_client.get("/api/sessions")).status_code == 401


async def test_a_session_from_the_history_opens_on_the_detail_route(
    api_client: httpx.AsyncClient,
) -> None:
    """The id the listing hands out is the one the detail route takes — the
    `extern_id` (ADR 0050) and not the primary key. Without this the history
    would list Sessions nobody could open."""
    persist(turns=MEASURED_TURNS, extern_id=uuid.uuid4())

    listed = (await api_client.get("/api/sessions")).json()["sessions"][0]
    detail = await api_client.get(f"/api/sessions/{listed['session_id']}")

    assert detail.status_code == 200
    assert detail.json()["session_id"] == listed["session_id"]
