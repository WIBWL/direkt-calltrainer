"""Storage consent: checked at write time, fails closed, withdrawal deletes (F-49, ADR 0066)."""

# pylint: disable=duplicate-code  # each module carries its own fixture Turns on purpose

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy.orm import Session as DbSession

from shared.db.models import Consent, Feedback, Session
from shared.turn import Turn
from backend import consent as consent_service
from backend.tests.conftest import TEST_AUTH, persist

pytestmark = pytest.mark.usefixtures("reference_data")

TURNS = [
    Turn(seq=1, persona_text="Brandt hier.", persona_offset_ms=0, persona_end_ms=1500),
    Turn(seq=2,
         user_text="Guten Tag!", user_offset_ms=1800, user_end_ms=2700,
         user_speech_ms=900, user_phonation_ms=700,
         persona_text="Zu teuer.", persona_offset_ms=3000, persona_end_ms=4100),
]


def _grant(db: DbSession, subject: str = TEST_AUTH.sub, *, version: str | None = None) -> None:
    """Record a granted decision directly, bypassing the route."""
    db.add(
        Consent(
            subject_id=subject,
            purpose=consent_service.PURPOSE,
            version=version or consent_service.CURRENT_VERSION,
            status="granted",
            decided_at=datetime.now(UTC),
        )
    )
    db.commit()


async def test_a_new_account_is_asked(api_client: httpx.AsyncClient) -> None:
    body = (await api_client.get("/api/consent")).json()

    assert body["status"] is None
    assert body["decision_required"] is True
    assert body["allows_storage"] is False


async def test_granting_is_recorded_and_reported(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post("/api/consent", json={"granted": True})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "granted"
    assert body["allows_storage"] is True
    assert body["decision_required"] is False
    assert body["version"] == body["current_version"]


async def test_a_withdrawal_is_not_asked_again(api_client: httpx.AsyncClient) -> None:
    await api_client.post("/api/consent", json={"granted": False})

    body = (await api_client.get("/api/consent")).json()

    assert body["status"] == "withdrawn"
    assert body["allows_storage"] is False
    assert body["decision_required"] is False


async def test_a_stale_version_is_asked_again(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    _grant(db_session, version="an-older-wording")

    body = (await api_client.get("/api/consent")).json()

    assert body["status"] == "granted"
    assert body["allows_storage"] is False
    assert body["decision_required"] is True


async def test_decisions_are_appended_not_overwritten(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    await api_client.post("/api/consent", json={"granted": True})
    await api_client.post("/api/consent", json={"granted": False})
    await api_client.post("/api/consent", json={"granted": True})

    rows = db_session.query(Consent).order_by(Consent.consent_id).all()

    assert [r.status for r in rows] == ["granted", "withdrawn", "granted"]


async def test_repeating_a_decision_writes_nothing(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    await api_client.post("/api/consent", json={"granted": True})
    await api_client.post("/api/consent", json={"granted": True})

    assert db_session.query(Consent).count() == 1


async def test_a_session_is_stored_once_consent_is_given(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    await api_client.post("/api/consent", json={"granted": True})

    persist(turns=TURNS)

    assert db_session.query(Session).count() == 1


async def test_a_session_is_not_stored_without_consent(
    app_database: str, db_session: DbSession  # pylint: disable=unused-argument
) -> None:
    # Imported here so a collection-time import does not pull in the live path.
    from backend.api import session_ws  # pylint: disable=import-outside-toplevel
    from backend.session import persistence  # pylint: disable=import-outside-toplevel

    await session_ws._record(persistence.FinishedCall(  # pylint: disable=protected-access
        extern_id=uuid.uuid4(), subject_id=TEST_AUTH.sub, persona=_persona(),
        scenario=_scenario(), turns=_orchestrator().turns, started_at=_started(), reason="user",
    ))

    assert db_session.query(Session).count() == 0


def test_the_writer_itself_refuses_without_consent(
    app_database: str, db_session: DbSession  # pylint: disable=unused-argument
) -> None:
    from backend.session import persistence  # pylint: disable=import-outside-toplevel

    written = persistence.persist_session(persistence.FinishedCall(
        extern_id=uuid.uuid4(), subject_id=TEST_AUTH.sub, persona=_persona(),
        scenario=_scenario(), turns=TURNS, started_at=_started(), reason="user",
    ))

    assert written is None
    assert db_session.query(Session).count() == 0


async def test_withdrawing_mid_call_still_prevents_the_write(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    from backend.api import session_ws  # pylint: disable=import-outside-toplevel
    from backend.session import persistence  # pylint: disable=import-outside-toplevel

    await api_client.post("/api/consent", json={"granted": True})
    # ... the call runs ...
    await api_client.post("/api/consent", json={"granted": False})

    await session_ws._record(persistence.FinishedCall(  # pylint: disable=protected-access
        extern_id=uuid.uuid4(), subject_id=TEST_AUTH.sub, persona=_persona(),
        scenario=_scenario(), turns=_orchestrator().turns, started_at=_started(), reason="user",
    ))

    assert db_session.query(Session).count() == 0


def test_an_unanswerable_question_fails_closed(monkeypatch) -> None:
    def explode():
        raise RuntimeError("database is gone")

    monkeypatch.setattr(consent_service, "session_scope", explode)

    assert consent_service.allows_storage("anyone") is False


async def test_withdrawing_deletes_what_was_stored(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    await api_client.post("/api/consent", json={"granted": True})
    persist(turns=TURNS)
    assert db_session.query(Session).count() == 1

    response = await api_client.post("/api/consent", json={"granted": False})

    assert response.json()["deleted_sessions"] == 1
    db_session.expire_all()
    assert db_session.query(Session).count() == 0


async def test_withdrawing_leaves_other_subjects_alone(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    await api_client.post("/api/consent", json={"granted": True})
    persist(turns=TURNS)
    persist(turns=TURNS, subject="somebody-else")

    await api_client.post("/api/consent", json={"granted": False})

    db_session.expire_all()
    remaining = db_session.query(Session).all()
    assert [s.subject_id for s in remaining] == ["somebody-else"]


async def test_withdrawing_removes_the_whole_subtree(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    await api_client.post("/api/consent", json={"granted": True})
    persist(turns=TURNS)
    stored = db_session.query(Session).one()
    db_session.add(
        Feedback(session_id=stored.session_id, summary="Zusammenfassung.",
                 created_at=datetime.now(UTC))
    )
    db_session.commit()

    await api_client.post("/api/consent", json={"granted": False})

    db_session.expire_all()
    assert db_session.query(Session).count() == 0
    assert db_session.query(Feedback).count() == 0


async def test_withdrawing_twice_is_not_an_error(
    api_client: httpx.AsyncClient,
) -> None:
    await api_client.post("/api/consent", json={"granted": True})
    persist(turns=TURNS)

    first = await api_client.post("/api/consent", json={"granted": False})
    second = await api_client.post("/api/consent", json={"granted": False})

    assert first.json()["deleted_sessions"] == 1
    assert second.status_code == 200
    assert second.json()["deleted_sessions"] == 0


async def test_consent_requires_a_token(api_client: httpx.AsyncClient) -> None:
    from backend import auth  # pylint: disable=import-outside-toplevel
    from backend.app import app  # pylint: disable=import-outside-toplevel

    app.dependency_overrides.pop(auth.require_user, None)

    assert (await api_client.get("/api/consent")).status_code == 401
    assert (await api_client.post("/api/consent", json={"granted": True})).status_code == 401


def _persona():
    from backend.tests.conftest import TEST_PERSONAS  # pylint: disable=import-outside-toplevel
    from dataclasses import replace  # pylint: disable=import-outside-toplevel
    from shared.tests.fixtures import PERSONA_KEY  # pylint: disable=import-outside-toplevel

    return replace(TEST_PERSONAS[0], id=PERSONA_KEY)


def _scenario():
    from backend.tests.conftest import TEST_SCENARIOS  # pylint: disable=import-outside-toplevel
    from shared.tests.fixtures import SCENARIO_KEY  # pylint: disable=import-outside-toplevel
    from dataclasses import replace  # pylint: disable=import-outside-toplevel

    return replace(TEST_SCENARIOS[0], id=SCENARIO_KEY)


def _orchestrator():
    """The bit of the orchestrator `_record` actually reads: its turns."""
    class _Stub:
        turns = TURNS

    return _Stub()


def _started():
    from shared.tests.fixtures import SESSION_STARTED  # pylint: disable=import-outside-toplevel

    return SESSION_STARTED


def test_a_withdrawal_under_an_older_version_still_blocks_the_write(
    app_database: str, db_session: DbSession  # pylint: disable=unused-argument
) -> None:
    from backend.session import persistence  # pylint: disable=import-outside-toplevel

    db_session.add(
        Consent(
            subject_id=TEST_AUTH.sub,
            purpose=consent_service.PURPOSE,
            version="an-older-wording",
            status="withdrawn",
            decided_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    state = consent_service.current(db_session, TEST_AUTH.sub)
    assert state.allows_storage is False, "a stale no is still a no"
    assert state.decision_required is False, "and is not asked again"

    written = persistence.persist_session(persistence.FinishedCall(
        extern_id=uuid.uuid4(), subject_id=TEST_AUTH.sub, persona=_persona(),
        scenario=_scenario(), turns=TURNS, started_at=_started(), reason="user",
    ))

    assert written is None
    assert db_session.query(Session).count() == 0
