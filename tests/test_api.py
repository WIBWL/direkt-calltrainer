"""The HTTP surface of a stored Session: status codes and the response shape
the frontend relies on (ADR 0050).

Covers the round trip that is the whole point of persisting a Session at all
(ADR 0034, F-12): write it through `persist_session`, read it back through
`GET /api/sessions/{extern_id}`, and get the same conversation out.

The schema is English but the wire is German: `sprecher`, `transkript` and the
rest are what frontend/src/protocol.ts declares, so they are asserted verbatim
here — a rename on this boundary is a frontend change, not a backend one.
"""
import uuid

import httpx
import pytest
from sqlalchemy.orm import Session as DbSession

from backend.db.models import Persona as DbPersona
from backend.db.models import Session
from backend.session.models import Turn
from tests.conftest import PERSONA_KEY, SCENARIO_KEY, persist

pytestmark = pytest.mark.usefixtures("reference_data")


def _store(extern_id: uuid.UUID) -> None:
    persist(
        extern_id=extern_id,
        turns=[
            Turn(seq=1, persona_text="Brandt hier.",
                 persona_offset_ms=0, persona_end_ms=1500),
            Turn(seq=2,
                 user_text="Guten Tag!", user_offset_ms=1800, user_end_ms=2700,
                 persona_text="Zu teuer.",
                 persona_offset_ms=3000, persona_end_ms=4100),
        ],
    )


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
    """The endpoint reads the persona table, not backend/personas.py (ADR 0041)
    — here it returns the Persona the fixture inserted, and the seed never
    ran, so a module-backed endpoint would answer differently."""
    response = await api_client.get("/api/personas")

    assert response.status_code == 200
    assert [p["id"] for p in response.json()] == [PERSONA_KEY]
    assert response.json()[0]["name"] == "Thomas Brandt"


async def test_scenarios_come_from_the_database(api_client: httpx.AsyncClient) -> None:
    """Same for Scenarios; the shape is the one App.tsx destructures, and `id`
    is the natural key the client sends back in session.start."""
    response = await api_client.get("/api/scenarios")

    assert response.status_code == 200
    assert set(response.json()[0]) == {"id", "name", "description"}
    assert response.json()[0]["id"] == SCENARIO_KEY


async def test_deactivated_persona_is_not_offered_for_a_new_call(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    """A retired Persona stays in the table for the Sessions that reference it,
    but must not appear in the selection."""
    db_session.query(DbPersona).update({"active": False})
    db_session.commit()

    response = await api_client.get("/api/personas")

    assert response.status_code == 200
    assert response.json() == []


async def test_unknown_session_is_a_clean_404(api_client: httpx.AsyncClient) -> None:
    """A stale id in a client's sessionStorage is expected, not exceptional."""
    response = await api_client.get(f"/api/sessions/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown session"


async def test_malformed_session_id_is_rejected(api_client: httpx.AsyncClient) -> None:
    """Anything that is not a UUID fails validation before a query runs."""
    response = await api_client.get("/api/sessions/not-a-uuid")

    assert response.status_code == 422


async def test_a_session_cannot_be_reached_through_its_primary_key(
    api_client: httpx.AsyncClient,
) -> None:
    """Only the public id opens a Session — the sequential primary key must not
    be usable as a lookup, or Sessions could be enumerated (ADR 0050)."""
    _store(uuid.uuid4())

    # The first Session has primary key 1; that value as a UUID finds nothing.
    response = await api_client.get(f"/api/sessions/{uuid.UUID(int=1)}")

    assert response.status_code == 404


async def test_stored_session_is_returned_in_the_transcript_shape(
    api_client: httpx.AsyncClient,
) -> None:
    """The payload has to carry the keys protocol.ts declares, so one view can
    render both a live and a reloaded Session."""
    extern_id = uuid.uuid4()
    _store(extern_id)

    response = await api_client.get(f"/api/sessions/{extern_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == str(extern_id)
    assert body["persona"] == "Thomas Brandt"
    assert body["szenario"] == "Kündigungsabsicht"
    assert set(body["turns"][0]) == {
        "turn_id", "sprecher", "start_offset_ms", "dauer_ms", "transkript",
    }


async def test_transcript_comes_back_in_speaking_order(
    api_client: httpx.AsyncClient,
) -> None:
    """seq_index carries the ordering, so the read path has to sort by it."""
    extern_id = uuid.uuid4()
    _store(extern_id)

    body = (await api_client.get(f"/api/sessions/{extern_id}")).json()

    assert [(t["sprecher"], t["transkript"]) for t in body["turns"]] == [
        ("persona", "Brandt hier."),
        ("nutzer", "Guten Tag!"),
        ("persona", "Zu teuer."),
    ]
    assert [t["dauer_ms"] for t in body["turns"]] == [1500, 900, 1100]


async def test_speaker_is_translated_back_to_the_wire_vocabulary(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    """The column is `speaker` in ('user', 'persona'); the wire says `sprecher`
    in ('nutzer', 'persona'), which TranscriptView.tsx compares against. The
    two must not be allowed to drift into each other."""
    extern_id = uuid.uuid4()
    _store(extern_id)

    stored = db_session.query(Session).one()
    assert {t.speaker for t in stored.turns} == {"user", "persona"}

    body = (await api_client.get(f"/api/sessions/{extern_id}")).json()
    assert {t["sprecher"] for t in body["turns"]} == {"nutzer", "persona"}


async def test_feedback_is_absent_until_the_worker_has_run(
    api_client: httpx.AsyncClient,
) -> None:
    """The Session becomes readable before its wrap-up exists (ADR 0019), and
    the client polls on `status` until it settles."""
    extern_id = uuid.uuid4()
    _store(extern_id)

    body = (await api_client.get(f"/api/sessions/{extern_id}")).json()

    assert body["feedback"] is None
    assert body["status"] == "queued"
