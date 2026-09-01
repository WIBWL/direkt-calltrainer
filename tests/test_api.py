"""The HTTP surface: status codes and response shapes the frontend relies on.

Everything below the routes is covered by the repository tests; what these add
is the layer nobody else exercises — that a missing Session is a clean 404 and
not a crash, that a malformed id is rejected before it reaches the database, and
that the transcript arrives in the shape the client already renders.
"""
import uuid

import httpx
import pytest
from sqlalchemy.orm import Session as DbSession

from backend.db import repository
from backend.session.models import Turn
from tests.conftest import PERSONA_KEY, SCENARIO_KEY, make_finished_session

pytestmark = pytest.mark.usefixtures("reference_data")


async def test_liveness_needs_no_database(api_client: httpx.AsyncClient) -> None:
    """/health must not depend on anything, or a brief database outage would
    look like a dead process and trigger a restart loop."""
    response = await api_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_reports_the_database(api_client: httpx.AsyncClient) -> None:
    """/health/ready is what the compose healthcheck asks, so it has to
    actually reach Postgres rather than answer from memory."""
    response = await api_client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


async def test_personas_come_from_the_database(api_client: httpx.AsyncClient) -> None:
    """The endpoint reads the persona table, not backend/personas.py — here it
    returns the Persona the fixture inserted, which the module does not know."""
    response = await api_client.get("/api/personas")

    assert response.status_code == 200
    assert [p["id"] for p in response.json()] == [PERSONA_KEY]
    assert response.json()[0]["name"] == "Thomas Brandt"


async def test_scenarios_come_from_the_database(api_client: httpx.AsyncClient) -> None:
    """Same for Scenarios; the shape is the one App.tsx destructures."""
    response = await api_client.get("/api/scenarios")

    assert response.status_code == 200
    assert set(response.json()[0]) == {"id", "name", "description"}


async def test_unknown_session_is_a_clean_404(api_client: httpx.AsyncClient) -> None:
    """A stale id in a client's localStorage is expected, not exceptional."""
    response = await api_client.get(f"/api/sessions/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown session"


async def test_malformed_session_id_is_rejected(api_client: httpx.AsyncClient) -> None:
    """Anything that is not a UUID fails validation before a query runs."""
    response = await api_client.get("/api/sessions/not-a-uuid")

    assert response.status_code == 422


async def test_stored_session_is_returned_in_the_transcript_shape(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    """The payload has to match what session.ended sends over the WebSocket, so
    one view can render both a live and a reloaded Session."""
    extern_id = uuid.uuid4()
    repository.save_session(
        db_session,
        make_finished_session(
            extern_id=extern_id,
            turns=[
                Turn(seq=1, persona_text="Brandt hier.", persona_duration_ms=1500),
                Turn(
                    seq=2,
                    user_text="Guten Tag!",
                    persona_text="Zu teuer.",
                    user_duration_ms=900,
                    persona_duration_ms=1100,
                ),
            ],
        ),
    )
    db_session.commit()

    response = await api_client.get(f"/api/sessions/{extern_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == str(extern_id)
    assert body["status"] == "completed"
    assert body["persona_name"] == "Thomas Brandt"
    assert body["scenario_name"] == "Kündigungsabsicht"
    assert [t["turn_seq"] for t in body["transcript"]] == [1, 2]
    assert set(body["transcript"][0]) == {
        "turn_seq",
        "user_text",
        "persona_text",
        "user_duration_ms",
        "persona_duration_ms",
    }


async def test_scenario_key_is_not_exposed_as_an_internal_id(
    api_client: httpx.AsyncClient,
) -> None:
    """`id` on the wire is the stable natural key, never the primary key —
    the client sends it straight back in session.start."""
    response = await api_client.get("/api/scenarios")

    assert response.json()[0]["id"] == SCENARIO_KEY
