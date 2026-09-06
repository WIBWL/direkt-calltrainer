"""Stored Sessions expire after six months (F-49, ADR 0061).

Two properties carry this file. The sweep has to delete what is over the line
and nothing else, which is the ordinary case; and it has to leave a subject who
suspended it entirely alone, which is the case nobody would notice being broken
until someone lost data they had asked to keep.

Time is injected rather than waited for: `sweep(db, now=...)` places the
boundary, so the tests are about the rule and not about the clock.
"""
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy.orm import Session as DbSession

from backend import retention
from backend.db.models import Feedback, RetentionPreference, Session, Turn
from backend.session.models import Turn as LiveTurn
from tests.conftest import TEST_AUTH, persist

pytestmark = pytest.mark.usefixtures("reference_data")

NOW = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)
# Either side of the boundary, by a day, so a test never turns on which way an
# exactly-equal comparison rounds.
JUST_INSIDE = NOW - retention.RETENTION + timedelta(days=1)
LONG_EXPIRED = NOW - retention.RETENTION - timedelta(days=30)

TURNS = [
    LiveTurn(seq=1, persona_text="Brandt hier.", persona_offset_ms=0, persona_end_ms=1500),
    LiveTurn(seq=2,
             user_text="Guten Tag!", user_offset_ms=1800, user_end_ms=2700,
             user_speech_ms=900, user_phonation_ms=700,
             persona_text="Zu teuer.", persona_offset_ms=3000, persona_end_ms=4100),
]


def test_the_period_is_six_months() -> None:
    """The number itself, pinned. Changing it is a policy decision and should
    fail a test rather than slip through as an edit."""
    assert retention.RETENTION == timedelta(days=182)


def test_an_expired_session_is_deleted(
    db_session: DbSession, app_database: str  # pylint: disable=unused-argument
) -> None:
    """The ordinary case: past the line, so it goes."""
    persist(turns=TURNS, started_at=LONG_EXPIRED)

    removed = retention.sweep(db_session, now=NOW)

    assert removed == 1
    assert db_session.query(Session).count() == 0


def test_a_session_inside_the_period_is_kept(
    db_session: DbSession, app_database: str  # pylint: disable=unused-argument
) -> None:
    """One day short of six months is still inside it. A sweep that took this
    would be deleting data people were promised they still had."""
    persist(turns=TURNS, started_at=JUST_INSIDE)

    removed = retention.sweep(db_session, now=NOW)

    assert removed == 0
    assert db_session.query(Session).count() == 1


def test_the_sweep_takes_the_whole_subtree(
    db_session: DbSession, app_database: str  # pylint: disable=unused-argument
) -> None:
    """A Session row disappearing while its transcript stays would be the
    deletion failing quietly in the direction that matters."""
    persist(turns=TURNS, started_at=LONG_EXPIRED)
    stored = db_session.query(Session).one()
    db_session.add(Feedback(session_id=stored.session_id, summary="Zusammenfassung.",
                            created_at=datetime.now(UTC)))
    db_session.commit()

    retention.sweep(db_session, now=NOW)

    assert db_session.query(Turn).count() == 0
    assert db_session.query(Feedback).count() == 0


def test_a_suspended_subject_keeps_everything(
    db_session: DbSession, app_database: str  # pylint: disable=unused-argument
) -> None:
    """The one that protects a promise. Someone who switched the sweep off has
    been told their trainings stay, and a sweep that ignored that would delete
    data on the strength of a setting the user explicitly changed."""
    persist(turns=TURNS, started_at=LONG_EXPIRED)
    retention.set_auto_delete(db_session, TEST_AUTH.sub, False)
    db_session.commit()

    removed = retention.sweep(db_session, now=NOW)

    assert removed == 0
    assert db_session.query(Session).count() == 1


def test_suspending_one_subject_does_not_spare_another(
    db_session: DbSession, app_database: str  # pylint: disable=unused-argument
) -> None:
    """The preference is per account. Read wrongly it would either spare
    everyone or nobody, and both look plausible in a one-user test."""
    persist(turns=TURNS, started_at=LONG_EXPIRED)
    persist(turns=TURNS, started_at=LONG_EXPIRED, subject="somebody-else")
    retention.set_auto_delete(db_session, TEST_AUTH.sub, False)
    db_session.commit()

    removed = retention.sweep(db_session, now=NOW)

    assert removed == 1
    remaining = db_session.query(Session).all()
    assert [s.subject_id for s in remaining] == [TEST_AUTH.sub]


def test_the_default_is_to_delete(db_session: DbSession) -> None:
    """No row means the period applies. If the default were the other way, a
    retention period would be something each account had to opt into, which is
    not a period at all."""
    assert retention.auto_delete_enabled(db_session, "never-decided") is True
    assert db_session.query(RetentionPreference).count() == 0


def test_the_choice_is_idempotent(db_session: DbSession) -> None:
    """Setting it twice leaves one row, not two — the column is unique, and a
    second row would make the sweep depend on which one it read."""
    retention.set_auto_delete(db_session, TEST_AUTH.sub, False)
    retention.set_auto_delete(db_session, TEST_AUTH.sub, False)
    db_session.commit()

    assert db_session.query(RetentionPreference).count() == 1
    assert retention.auto_delete_enabled(db_session, TEST_AUTH.sub) is False


def test_switching_back_on_deletes_nothing_immediately(
    db_session: DbSession, app_database: str  # pylint: disable=unused-argument
) -> None:
    """Re-enabling is a statement about the future, not an action. The next
    sweep applies the period as it always would; the click itself must not
    remove anything, or the control would be a delete button in disguise."""
    persist(turns=TURNS, started_at=LONG_EXPIRED)
    retention.set_auto_delete(db_session, TEST_AUTH.sub, False)
    retention.set_auto_delete(db_session, TEST_AUTH.sub, True)
    db_session.commit()

    assert db_session.query(Session).count() == 1


def test_sweeping_twice_finds_nothing_the_second_time(
    db_session: DbSession, app_database: str  # pylint: disable=unused-argument
) -> None:
    """Idempotent, which is what makes it safe to run on a schedule and by
    hand at the same time."""
    persist(turns=TURNS, started_at=LONG_EXPIRED)

    assert retention.sweep(db_session, now=NOW) == 1
    assert retention.sweep(db_session, now=NOW) == 0


def test_next_expiry_names_the_oldest_session(
    db_session: DbSession, app_database: str  # pylint: disable=unused-argument
) -> None:
    """What the profile page shows. The oldest one is the next to go, so that
    is the date the user needs."""
    older = NOW - timedelta(days=100)
    persist(turns=TURNS, started_at=NOW - timedelta(days=10))
    persist(turns=TURNS, started_at=older)

    due = retention.next_expiry(db_session, TEST_AUTH.sub)

    assert due == older + retention.RETENTION


def test_next_expiry_is_silent_when_suspended(
    db_session: DbSession, app_database: str  # pylint: disable=unused-argument
) -> None:
    """No date, because there is not going to be one. Naming a date under a
    suspended sweep would be the interface contradicting itself."""
    persist(turns=TURNS, started_at=NOW - timedelta(days=10))
    retention.set_auto_delete(db_session, TEST_AUTH.sub, False)
    db_session.commit()

    assert retention.next_expiry(db_session, TEST_AUTH.sub) is None


# --- Over the wire -----------------------------------------------------------


async def test_the_overview_reports_the_period(api_client: httpx.AsyncClient) -> None:
    """The profile page reads this to say when the next training goes."""
    persist(turns=TURNS, started_at=datetime(2026, 8, 1, tzinfo=UTC))

    body = (await api_client.get("/api/me/data")).json()

    assert body["retention"]["auto_delete"] is True
    assert body["retention"]["retention_days"] == retention.RETENTION.days
    assert body["retention"]["next_expiry_at"] is not None


async def test_the_switch_travels_over_the_wire(
    api_client: httpx.AsyncClient, db_session: DbSession
) -> None:
    persist(turns=TURNS, started_at=datetime(2026, 8, 1, tzinfo=UTC))

    off = await api_client.post("/api/me/retention", json={"auto_delete": False})

    assert off.status_code == 200
    assert off.json()["auto_delete"] is False
    assert off.json()["next_expiry_at"] is None
    db_session.expire_all()
    assert retention.auto_delete_enabled(db_session, TEST_AUTH.sub) is False


async def test_the_retention_route_needs_a_token(api_client: httpx.AsyncClient) -> None:
    """It changes how long someone's data is kept; without a caller there is no
    account to change it for (ADR 0009)."""
    from backend import auth  # pylint: disable=import-outside-toplevel
    from backend.app import app  # pylint: disable=import-outside-toplevel

    app.dependency_overrides.pop(auth.require_user, None)

    response = await api_client.post("/api/me/retention", json={"auto_delete": False})

    assert response.status_code == 401
