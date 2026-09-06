"""Storage consent and what follows from withdrawing it (F-49, ADR 0060).

The decisive test in this file is `test_a_session_is_not_stored_without_consent`
— everything else describes bookkeeping, that one is the only thing standing
between a subject who said no and a stored record of their call.

Two properties get their own tests because neither is visible in a happy path:
the check is made when the Session is written rather than when it starts, so a
withdrawal *during* a call still takes effect; and it fails closed, so a
database that cannot answer the question does not get the benefit of the doubt.
"""
import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy.orm import Session as DbSession

from backend import consent as consent_service
from backend.db.models import Consent, Feedback, Session
from backend.session.models import Turn
from tests.conftest import TEST_AUTH, persist

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


# --- What the client is told -------------------------------------------------


async def test_a_new_account_is_asked(api_client: httpx.AsyncClient) -> None:
    """No decision on record means the interface has to ask before anything
    this subject does can be stored."""
    body = (await api_client.get("/api/consent")).json()

    assert body["status"] is None
    assert body["decision_required"] is True
    assert body["allows_storage"] is False


async def test_granting_is_recorded_and_reported(api_client: httpx.AsyncClient) -> None:
    """A "yes" comes back as the state that now holds, so the interface does
    not have to re-fetch to know what it just did."""
    response = await api_client.post("/api/consent", json={"granted": True})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "granted"
    assert body["allows_storage"] is True
    assert body["decision_required"] is False
    assert body["version"] == body["current_version"]


async def test_a_withdrawal_is_not_asked_again(api_client: httpx.AsyncClient) -> None:
    """A "no" is a decision, not a gap in one. Re-prompting someone who just
    declined would turn the dialog into a way of wearing them down."""
    await api_client.post("/api/consent", json={"granted": False})

    body = (await api_client.get("/api/consent")).json()

    assert body["status"] == "withdrawn"
    assert body["allows_storage"] is False
    assert body["decision_required"] is False


async def test_a_stale_version_is_asked_again(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    """Agreeing to an older notice is not agreeing to this one, so a changed
    wording invalidates the decision instead of silently inheriting it."""
    _grant(db_session, version="an-older-wording")

    body = (await api_client.get("/api/consent")).json()

    assert body["status"] == "granted"
    assert body["allows_storage"] is False
    assert body["decision_required"] is True


# --- The decision log --------------------------------------------------------


async def test_decisions_are_appended_not_overwritten(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    """Granting, withdrawing and granting again leaves three rows. A record
    that overwrites itself destroys the evidence it exists to keep."""
    await api_client.post("/api/consent", json={"granted": True})
    await api_client.post("/api/consent", json={"granted": False})
    await api_client.post("/api/consent", json={"granted": True})

    rows = db_session.query(Consent).order_by(Consent.consent_id).all()

    assert [r.status for r in rows] == ["granted", "withdrawn", "granted"]


async def test_repeating_a_decision_writes_nothing(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    """Idempotent where it counts: a double-clicked button must not fill the
    log with identical rows."""
    await api_client.post("/api/consent", json={"granted": True})
    await api_client.post("/api/consent", json={"granted": True})

    assert db_session.query(Consent).count() == 1


# --- The gate ----------------------------------------------------------------


async def test_a_session_is_stored_once_consent_is_given(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    """The other side of the gate: with consent, nothing changes."""
    await api_client.post("/api/consent", json={"granted": True})

    persist(turns=TURNS)

    assert db_session.query(Session).count() == 1


async def test_a_session_is_not_stored_without_consent(
    app_database: str, db_session: DbSession  # pylint: disable=unused-argument
) -> None:
    """The one that matters. Persisting is guarded at the point of writing, so
    a subject who never agreed leaves no stored record of their call.

    Driven through `_record`, the WebSocket layer's own write path, rather than
    through `persist_session` — the guard lives in the caller, and a test that
    called the writer directly would pass while the guard did nothing.

    `app_database` is requested for its effect and not its value, and it is
    load-bearing: without it `session_scope()` cannot reach a database at all,
    the write fails on its own, and this test goes green whether the guard
    exists or not. It did exactly that until a mutation run caught it.
    """
    # Imported here so a collection-time import does not pull in the live path.
    from backend.api import session_ws  # pylint: disable=import-outside-toplevel

    await session_ws._record(  # pylint: disable=protected-access
        uuid.uuid4(), TEST_AUTH.sub, _persona(), _scenario(), _orchestrator(), _started(), "user",
    )

    assert db_session.query(Session).count() == 0


async def test_withdrawing_mid_call_still_prevents_the_write(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    """Consent is read when the Session is written, not when it starts.

    A call can run for minutes. If the check happened at the handshake, its
    answer would be that old by the time the row is written, and someone who
    withdrew while talking would find the call stored anyway.
    """
    from backend.api import session_ws  # pylint: disable=import-outside-toplevel

    await api_client.post("/api/consent", json={"granted": True})
    # ... the call runs ...
    await api_client.post("/api/consent", json={"granted": False})

    await session_ws._record(  # pylint: disable=protected-access
        uuid.uuid4(), TEST_AUTH.sub, _persona(), _scenario(), _orchestrator(), _started(), "user",
    )

    assert db_session.query(Session).count() == 0


def test_an_unanswerable_question_fails_closed(monkeypatch) -> None:
    """A database that cannot be reached must not be read as "go ahead".

    Everywhere else a database failure is logged and stepped over, because
    losing a wrap-up beats losing a call. Here that same reflex would store
    data on a guess, which is the single outcome consent exists to prevent —
    so this is the one place that fails the other way.
    """
    def explode():
        raise RuntimeError("database is gone")

    monkeypatch.setattr(consent_service, "session_scope", explode)

    assert consent_service.allows_storage("anyone") is False


# --- Withdrawal deletes ------------------------------------------------------


async def test_withdrawing_deletes_what_was_stored(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    """Consent is the only basis this application has for keeping the data, so
    once it is withdrawn there is nothing left to justify keeping it."""
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
    """The delete is scoped to the caller. Nothing else would be recoverable."""
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
    """Turns, measurements and the wrap-up go with the Session — the cascades
    are what make a deletion complete rather than a Session row disappearing
    while its transcript stays behind."""
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
    """A retried withdrawal finds nothing to delete and says so, rather than
    failing for work that already succeeded."""
    await api_client.post("/api/consent", json={"granted": True})
    persist(turns=TURNS)

    first = await api_client.post("/api/consent", json={"granted": False})
    second = await api_client.post("/api/consent", json={"granted": False})

    assert first.json()["deleted_sessions"] == 1
    assert second.status_code == 200
    assert second.json()["deleted_sessions"] == 0


async def test_consent_requires_a_token(api_client: httpx.AsyncClient) -> None:
    """Both routes act on the caller's own `sub`; without one there is no
    request to answer (ADR 0009)."""
    from backend import auth  # pylint: disable=import-outside-toplevel
    from backend.app import app  # pylint: disable=import-outside-toplevel

    app.dependency_overrides.pop(auth.require_user, None)

    assert (await api_client.get("/api/consent")).status_code == 401
    assert (await api_client.post("/api/consent", json={"granted": True})).status_code == 401


# --- Helpers -----------------------------------------------------------------


def _persona():
    from tests.conftest import TEST_PERSONAS  # pylint: disable=import-outside-toplevel
    from dataclasses import replace  # pylint: disable=import-outside-toplevel
    from tests.conftest import PERSONA_KEY  # pylint: disable=import-outside-toplevel

    return replace(TEST_PERSONAS[0], id=PERSONA_KEY)


def _scenario():
    from tests.conftest import TEST_SCENARIOS, SCENARIO_KEY  # pylint: disable=import-outside-toplevel
    from dataclasses import replace  # pylint: disable=import-outside-toplevel

    return replace(TEST_SCENARIOS[0], id=SCENARIO_KEY)


def _orchestrator():
    """The bit of the orchestrator `_record` actually reads: its turns."""
    class _Stub:
        turns = TURNS

    return _Stub()


def _started():
    from tests.conftest import SESSION_STARTED  # pylint: disable=import-outside-toplevel

    return SESSION_STARTED
