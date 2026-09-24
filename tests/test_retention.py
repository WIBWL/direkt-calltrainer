"""Stored Sessions expire after six months (F-49, ADR 0067).

The sweep deletes what is over the line and nothing else, and leaves a subject who
suspended it alone. `sweep(db, now=...)` injects the time, so tests are about the rule.
"""
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy.orm import Session as DbSession

from backend import deletion, retention
from backend.db.models import (Feedback, RetentionPreference, Scenario, Session,
                               STATUS_COMPLETED, Turn)
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
    """The preference is readable and writable over the API."""
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


def _reverse_of(db: DbSession, session_id: int, created_at: datetime | None = None) -> int:
    """A reverse Scenario replaying that Session, shaped as reversals.py writes one.

    `created_at` matters: an orphaned reverse is found by its own age."""
    row = Scenario(
        key=None,
        title="Rollentausch",
        short_description="kurz",
        description="lang",
        case_facts="Fakten",
        call_goal="Ziel",
        briefing="",
        active=True,
        visibility="private",
        created_by=TEST_AUTH.sub,
        reverse=True,
        origin_session_id=session_id,
        reverse_brief={"goals": []},
        **({"created_at": created_at} if created_at else {}),
    )
    db.add(row)
    db.flush()
    return row.scenario_id


def test_an_expired_session_takes_its_reverse_with_it(
    db_session: DbSession, app_database: str  # pylint: disable=unused-argument
) -> None:
    """A reverse's briefing comes from the call's wrap-up, so it expires with the call
    (ADR 0070's addendum to ADR 0067) instead of outliving its origin.
    """
    extern_id = persist(turns=TURNS, started_at=LONG_EXPIRED)
    origin = db_session.query(Session).filter_by(extern_id=extern_id).one()
    reverse_id = _reverse_of(db_session, origin.session_id)

    removed = retention.sweep(db_session, now=NOW)

    assert removed == 1
    assert db_session.get(Scenario, reverse_id) is None


def test_a_reverse_someone_still_plays_survives_the_sweep(
    db_session: DbSession, app_database: str  # pylint: disable=unused-argument
) -> None:
    """The origin expires, a younger Session played on the reverse does not.

    `session.scenario_id` has no `ondelete` (ADR 0052), so deleting the reverse now
    would fail the whole sweep for every subject; it is left for a later run.
    """
    extern_id = persist(turns=TURNS, started_at=LONG_EXPIRED)
    origin = db_session.query(Session).filter_by(extern_id=extern_id).one()
    reverse_id = _reverse_of(db_session, origin.session_id)
    db_session.add(
        Session(
            extern_id=uuid.uuid4(),
            subject_id=TEST_AUTH.sub,
            persona_id=origin.persona_id,
            scenario_id=reverse_id,
            language_code=origin.language_code,
            status=STATUS_COMPLETED,
            started_at=JUST_INSIDE,
        )
    )
    db_session.flush()

    removed = retention.sweep(db_session, now=NOW)

    assert removed == 1, "only the expired origin should go"
    assert db_session.get(Scenario, reverse_id) is not None


def test_a_spared_reverse_goes_once_nothing_plays_it_any_more(
    db_session: DbSession, app_database: str  # pylint: disable=unused-argument
) -> None:
    """The later run does remove it (ADR 0067/0070).

    Found by `origin_session_id` alone, the reverse became invisible once the first
    run nulled that link, and its briefing outlived the period indefinitely.
    """
    extern_id = persist(turns=TURNS, started_at=LONG_EXPIRED)
    origin = db_session.query(Session).filter_by(extern_id=extern_id).one()
    reverse_id = _reverse_of(db_session, origin.session_id, created_at=LONG_EXPIRED)
    db_session.add(
        Session(
            extern_id=uuid.uuid4(),
            subject_id=TEST_AUTH.sub,
            persona_id=origin.persona_id,
            scenario_id=reverse_id,
            language_code=origin.language_code,
            status=STATUS_COMPLETED,
            started_at=JUST_INSIDE,
        )
    )
    db_session.flush()

    assert retention.sweep(db_session, now=NOW) == 1
    assert db_session.get(Scenario, reverse_id) is not None, "still played, so still here"

    # A year on, the younger Session has expired as well.
    later = NOW + timedelta(days=365)

    assert retention.sweep(db_session, now=later) == 1
    assert db_session.get(Scenario, reverse_id) is None, "nothing plays it now"


def test_a_reverse_whose_origin_was_deleted_by_hand_still_expires(
    db_session: DbSession, app_database: str  # pylint: disable=unused-argument
) -> None:
    """A single deletion leaves its reverse behind, but that reverse must still expire.

    With its origin gone no link remains, so it is found by its own age.
    """
    extern_id = persist(turns=TURNS, started_at=LONG_EXPIRED)
    origin = db_session.query(Session).filter_by(extern_id=extern_id).one()
    reverse_id = _reverse_of(db_session, origin.session_id, created_at=LONG_EXPIRED)

    deletion.delete_session(db_session, TEST_AUTH.sub, extern_id)
    db_session.flush()
    assert db_session.get(Scenario, reverse_id) is not None, "the single delete keeps it"

    retention.sweep(db_session, now=NOW)

    assert db_session.get(Scenario, reverse_id) is None


def test_a_young_orphaned_reverse_is_left_alone(
    db_session: DbSession, app_database: str  # pylint: disable=unused-argument
) -> None:
    """Age is the test, not orphanhood. A reverse written last week whose origin
    the User deleted yesterday is inside the period like anything else."""
    extern_id = persist(turns=TURNS, started_at=JUST_INSIDE)
    origin = db_session.query(Session).filter_by(extern_id=extern_id).one()
    reverse_id = _reverse_of(db_session, origin.session_id, created_at=JUST_INSIDE)

    deletion.delete_session(db_session, TEST_AUTH.sub, extern_id)
    db_session.flush()
    retention.sweep(db_session, now=NOW)

    assert db_session.get(Scenario, reverse_id) is not None
