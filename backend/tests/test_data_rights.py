"""Overview, export and deletion of one's own data (F-49, ADR 0066)."""

# pylint: disable=duplicate-code  # each module carries its own fixture Turns on purpose

import json
import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy.orm import Session as DbSession

from shared.db.models import Feedback, FeedbackPoint, Scenario, Session, Turn
from shared.turn import Turn as LiveTurn
from backend.tests.conftest import TEST_AUTH, persist

pytestmark = pytest.mark.usefixtures("reference_data")

TURNS = [
    LiveTurn(seq=1, persona_text="Brandt hier.", persona_offset_ms=0, persona_end_ms=1500),
    LiveTurn(seq=2,
             user_text="Guten Tag!", user_offset_ms=1800, user_end_ms=2700,
             user_speech_ms=900, user_phonation_ms=700,
             persona_text="Zu teuer.", persona_offset_ms=3000, persona_end_ms=4100),
]


def _add_feedback(db: DbSession) -> None:
    """Give the newest stored Session a wrap-up, the way the worker would."""
    session_id = db.query(Session).order_by(Session.session_id.desc()).first().session_id
    feedback = Feedback(
        session_id=session_id, summary="Zusammenfassung.",
        phase_language="Warm, dann sachlich.", created_at=datetime.now(UTC),
    )
    feedback.points = [
        FeedbackPoint(position=0, kind="strength", text="Klar formuliert."),
        FeedbackPoint(position=1, kind="improvement", text="Kürzer antworten."),
    ]
    db.add(feedback)
    db.commit()


async def test_overview_is_empty_for_a_new_account(api_client: httpx.AsyncClient) -> None:
    body = (await api_client.get("/api/me/data")).json()

    assert body["sessions"] == 0
    assert body["utterances"] == 0
    assert body["first_session_at"] is None


async def test_overview_counts_what_is_stored(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    persist(turns=TURNS)
    _add_feedback(db_session)

    body = (await api_client.get("/api/me/data")).json()

    assert body["sessions"] == 1
    assert body["utterances"] == 3  # two persona lines, one user line
    assert body["measurements"] == 1
    assert body["feedbacks"] == 1
    assert body["first_session_at"] is not None
    assert body["last_session_at"] == body["first_session_at"]


async def test_overview_ignores_other_subjects(api_client: httpx.AsyncClient) -> None:
    persist(turns=TURNS)
    persist(turns=TURNS, subject="somebody-else")
    persist(turns=TURNS, subject="somebody-else")

    body = (await api_client.get("/api/me/data")).json()

    assert body["sessions"] == 1
    assert body["utterances"] == 3


async def test_export_carries_everything_that_was_stored(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    persist(turns=TURNS)
    _add_feedback(db_session)

    body = (await api_client.get("/api/me/export")).json()

    assert len(body["sessions"]) == db_session.query(Session).count()
    exported = body["sessions"][0]
    assert len(exported["transcript"]) == db_session.query(Turn).count()
    assert [line["text"] for line in exported["transcript"]] == [
        t.transcript for t in db_session.query(Turn).order_by(Turn.seq_index).all()
    ]
    assert exported["feedback"]["summary"] == "Zusammenfassung."
    assert exported["feedback"]["phase_language"] == "Warm, dann sachlich."
    assert len(exported["feedback"]["points"]) == 2
    assert exported["measurements"][0]["value"] > 0


async def test_the_export_reaches_past_the_sessions(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    persist(turns=TURNS)
    await api_client.put("/api/focus", json={"goals": ["pace"], "role": "sales",
                                             "categories": ["pricing"]})
    await api_client.post("/api/me/retention", json={"auto_delete": False})
    db_session.add(Scenario(
        key=None, title="Selbst verfasst", short_description="kurz",
        description="lang", case_facts="Fakten", call_goal="Ziel", briefing="",
        active=True, visibility="private", created_by=TEST_AUTH.sub, reverse=False,
    ))
    db_session.commit()

    body = (await api_client.get("/api/me/export")).json()

    assert body["focus"]["goals"] == ["pace"]
    assert body["focus"]["role"] == "sales"
    assert body["focus"]["call_types"] == ["pricing"]
    assert body["retention"]["auto_delete"] is False
    assert [s["title"] for s in body["scenarios"]] == ["Selbst verfasst"]
    assert body["scenarios"][0]["kind"] == "authored"


async def test_the_export_tells_the_three_segments_of_a_metric_apart(
    api_client: httpx.AsyncClient, db_session: DbSession  # pylint: disable=unused-argument
) -> None:
    persist(turns=TURNS)

    body = (await api_client.get("/api/me/export")).json()

    measurements = body["sessions"][0]["measurements"]
    assert measurements, "the call should have been measured at all"
    assert all("segment" in m for m in measurements)


async def test_export_is_a_download_not_a_page(api_client: httpx.AsyncClient) -> None:
    persist(turns=TURNS)

    response = await api_client.get("/api/me/export")

    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    assert ".json" in response.headers["content-disposition"]


async def test_export_holds_no_other_subjects_data(
    api_client: httpx.AsyncClient,
) -> None:
    persist(turns=TURNS)
    persist(
        turns=[LiveTurn(seq=1, user_text="Streng geheim, fremdes Gespräch.",
                        user_offset_ms=0, user_end_ms=900, user_speech_ms=900,
                        user_phonation_ms=700)],
        subject="somebody-else",
    )

    body = (await api_client.get("/api/me/export")).json()

    assert len(body["sessions"]) == 1
    assert "Streng geheim" not in json.dumps(body, ensure_ascii=False)


async def test_export_states_the_pseudonym_it_is_filed_under(
    api_client: httpx.AsyncClient,
) -> None:
    body = (await api_client.get("/api/me/export")).json()

    assert body["subject_id"]
    assert "consent" in body


async def test_a_training_can_be_deleted_on_its_own(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    kept = persist(turns=TURNS)
    doomed = persist(turns=TURNS)

    response = await api_client.delete(f"/api/sessions/{doomed}")

    assert response.status_code == 204
    db_session.expire_all()
    remaining = [str(s.extern_id) for s in db_session.query(Session).all()]
    assert remaining == [str(kept)]


async def test_deleting_a_training_takes_its_subtree(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    extern_id = persist(turns=TURNS)
    _add_feedback(db_session)

    await api_client.delete(f"/api/sessions/{extern_id}")

    db_session.expire_all()
    assert db_session.query(Turn).count() == 0
    assert db_session.query(Feedback).count() == 0
    assert db_session.query(FeedbackPoint).count() == 0


async def test_another_users_training_cannot_be_deleted(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    extern_id = persist(turns=TURNS, subject="somebody-else")

    response = await api_client.delete(f"/api/sessions/{extern_id}")

    assert response.status_code == 404
    db_session.expire_all()
    assert db_session.query(Session).count() == 1


async def test_deleting_an_unknown_training_is_a_clean_404(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.delete(f"/api/sessions/{uuid.uuid4()}")

    assert response.status_code == 404


async def test_deleting_twice_reports_the_second_as_unknown(
    api_client: httpx.AsyncClient,
) -> None:
    extern_id = persist(turns=TURNS)

    assert (await api_client.delete(f"/api/sessions/{extern_id}")).status_code == 204
    assert (await api_client.delete(f"/api/sessions/{extern_id}")).status_code == 404


@pytest.mark.parametrize(
    "method, path",
    [("GET", "/api/me/data"), ("GET", "/api/me/export"), ("DELETE", "/api/sessions/{}")],
)
async def test_every_data_route_needs_a_token(
    api_client: httpx.AsyncClient, method: str, path: str
) -> None:
    from backend import auth  # pylint: disable=import-outside-toplevel
    from backend.app import app  # pylint: disable=import-outside-toplevel

    app.dependency_overrides.pop(auth.require_user, None)

    response = await api_client.request(method, path.format(uuid.uuid4()))

    assert response.status_code == 401
