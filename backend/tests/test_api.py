"""A stored Session over HTTP: status codes, ownership and shape (F-12, ADR 0034, 0050, 0057)."""

# pylint: disable=duplicate-code  # each module carries its own fixture Turns on purpose

import uuid
from datetime import datetime

import httpx
import pytest
from sqlalchemy.orm import Session as DbSession

from shared.db.models import Feedback, FeedbackPoint
from shared.db.models import Persona as DbPersona
from shared.db.models import Session
from shared.turn import Turn
from shared.tests.fixtures import METRIC_KEY
from backend.tests.conftest import persist

pytestmark = pytest.mark.usefixtures("reference_data")


def _store(extern_id: uuid.UUID) -> None:
    persist(
        extern_id=extern_id,
        turns=[
            Turn(seq=1, persona_text="Brandt hier.",
                 persona_offset_ms=0, persona_end_ms=1500),
            # Both durations: speaking pace, the one metric type the reference
            # fixture seeds, is a rate over phonation.
            Turn(seq=2,
                 user_text="Guten Tag!", user_offset_ms=1800, user_end_ms=2700,
                 user_speech_ms=900, user_phonation_ms=700,
                 persona_text="Zu teuer.",
                 persona_offset_ms=3000, persona_end_ms=4100),
        ],
    )


async def test_liveness_needs_no_database(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_reports_the_database(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


async def test_personas_come_from_the_database(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/api/personas")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "Thomas Brandt"
    assert uuid.UUID(body[0]["id"])  # extern_id, not the slug (ADR 0058)


async def test_scenarios_come_from_the_database(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/api/scenarios")

    assert response.status_code == 200
    entry = response.json()[0]
    assert set(entry) == {
        "id", "name", "short_description", "briefing", "description",
        "category", "origin", "shared", "follow_up",
        # ADR 0070: which side of the phone this Scenario puts the User on,
        # and the conversation a reverse replays.
        "reverse", "origin_session",
        # F-62: why a suggested card is suggested; null for the rest.
        "recommendation",
    }
    assert uuid.UUID(entry["id"])  # extern_id the client sends back in session.start
    assert entry["name"] == "Kündigungsabsicht"


async def test_deactivated_persona_is_not_offered_for_a_new_call(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    db_session.query(DbPersona).update({"active": False})
    db_session.commit()

    response = await api_client.get("/api/personas")

    assert response.status_code == 200
    assert response.json() == []


async def test_unknown_session_is_a_clean_404(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get(f"/api/sessions/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown session"


async def test_malformed_session_id_is_rejected(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/api/sessions/not-a-uuid")

    assert response.status_code == 422


async def test_a_session_cannot_be_reached_through_its_primary_key(
    api_client: httpx.AsyncClient,
) -> None:
    _store(uuid.uuid4())

    # The first Session has primary key 1; that value as a UUID finds nothing.
    response = await api_client.get(f"/api/sessions/{uuid.UUID(int=1)}")

    assert response.status_code == 404


async def test_another_users_session_is_not_readable(api_client: httpx.AsyncClient) -> None:
    extern_id = persist(subject="somebody-else")

    response = await api_client.get(f"/api/sessions/{extern_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown session"


async def test_stored_session_is_returned_in_the_transcript_shape(
    api_client: httpx.AsyncClient,
) -> None:
    extern_id = uuid.uuid4()
    _store(extern_id)

    response = await api_client.get(f"/api/sessions/{extern_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == str(extern_id)
    assert body["persona"] == "Thomas Brandt"
    assert body["scenario"] == "Kündigungsabsicht"
    # The exact key set, so an addition is a decision rather than drift.
    assert set(body["turns"][0]) == {
        "turn_id", "speaker", "start_offset_ms", "duration_ms", "transcript",
        "interrupted", "unheard_text",
    }


async def test_transcript_comes_back_in_speaking_order(
    api_client: httpx.AsyncClient,
) -> None:
    extern_id = uuid.uuid4()
    _store(extern_id)

    body = (await api_client.get(f"/api/sessions/{extern_id}")).json()

    assert [(t["speaker"], t["transcript"]) for t in body["turns"]] == [
        ("persona", "Brandt hier."),
        ("user", "Guten Tag!"),
        ("persona", "Zu teuer."),
    ]
    assert [t["duration_ms"] for t in body["turns"]] == [1500, 900, 1100]


async def test_speaker_matches_the_schema_vocabulary(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    extern_id = uuid.uuid4()
    _store(extern_id)

    stored = db_session.query(Session).one()
    assert {t.speaker for t in stored.turns} == {"user", "persona"}

    body = (await api_client.get(f"/api/sessions/{extern_id}")).json()
    assert {t["speaker"] for t in body["turns"]} == {"user", "persona"}


async def test_measurements_reach_the_wire_with_the_schema_vocabulary(
    api_client: httpx.AsyncClient,
) -> None:
    extern_id = uuid.uuid4()
    _store(extern_id)

    body = (await api_client.get(f"/api/sessions/{extern_id}")).json()

    assert len(body["measurements"]) == 1
    measurement = body["measurements"][0]
    assert set(measurement) == {"key", "name", "unit", "aspect", "value", "detail"}
    assert measurement["key"] == METRIC_KEY
    assert measurement["value"] > 0
    # The grouping the metrics slider switches on.
    assert measurement["aspect"] == "how"


@pytest.mark.parametrize(
    "stored, expected",
    [
        ("Im Einstieg klangen Sie warm, zum Abschluss sachlich.",
         "Im Einstieg klangen Sie warm, zum Abschluss sachlich."),
        (None, None),
    ],
    ids=["analysed", "not analysed"],
)
async def test_phase_block_reaches_the_wire_as_phase_language(
    api_client: httpx.AsyncClient,
    db_session: DbSession,
    stored: str | None,
    expected: str | None,
) -> None:
    extern_id = uuid.uuid4()
    _store(extern_id)
    session_id = db_session.query(Session).one().session_id
    db_session.add(
        Feedback(
            session_id=session_id,
            summary="Zusammenfassung.",
            phase_language=stored,
            created_at=datetime.now(),
        )
    )
    db_session.commit()

    body = (await api_client.get(f"/api/sessions/{extern_id}")).json()

    assert body["feedback"]["phase_language"] == expected


@pytest.mark.parametrize(
    "stored, expected",
    [
        ("Eine Störungsmeldung verlangt ruhige Sachlichkeit.",
         "Eine Störungsmeldung verlangt ruhige Sachlichkeit."),
        (None, None),
    ],
    ids=["analysed", "not analysed"],
)
async def test_tone_fit_reaches_the_wire_under_its_own_key(
    api_client: httpx.AsyncClient,
    db_session: DbSession,
    stored: str | None,
    expected: str | None,
) -> None:
    extern_id = uuid.uuid4()
    _store(extern_id)
    session_id = db_session.query(Session).one().session_id
    db_session.add(
        Feedback(
            session_id=session_id,
            summary="Zusammenfassung.",
            tone_fit=stored,
            created_at=datetime.now(),
        )
    )
    db_session.commit()

    body = (await api_client.get(f"/api/sessions/{extern_id}")).json()

    assert body["feedback"]["tone_fit"] == expected


async def test_feedback_points_reach_the_wire_with_the_schema_vocabulary(
    api_client: httpx.AsyncClient,
    db_session: DbSession,
) -> None:
    extern_id = uuid.uuid4()
    _store(extern_id)
    session_id = db_session.query(Session).one().session_id
    feedback = Feedback(
        session_id=session_id, summary="Zusammenfassung.", created_at=datetime.now(),
    )
    feedback.points = [
        FeedbackPoint(position=0, kind="strength", text="Klar formuliert."),
        FeedbackPoint(position=1, kind="improvement", text="Kürzer antworten."),
    ]
    db_session.add(feedback)
    db_session.commit()

    body = (await api_client.get(f"/api/sessions/{extern_id}")).json()

    assert [(p["kind"], p["text"]) for p in body["feedback"]["points"]] == [
        ("strength", "Klar formuliert."),
        ("improvement", "Kürzer antworten."),
    ]


async def test_feedback_is_absent_until_the_worker_has_run(
    api_client: httpx.AsyncClient,
) -> None:
    extern_id = uuid.uuid4()
    _store(extern_id)

    body = (await api_client.get(f"/api/sessions/{extern_id}")).json()

    assert body["feedback"] is None
    assert body["status"] == "queued"
