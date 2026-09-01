"""Deleting a Session must take its whole subtree with it and leave the shared
reference data alone.

This is the mechanism behind ADR 0034's promise that a User can delete their own
data. The cascades are declared at ORM level only (`cascade="all, delete-orphan"`)
— the foreign keys carry no `ON DELETE`, so this works through the ORM and not
through raw SQL. That distinction is exactly what these tests pin down, including
the awkward case: a FeedbackPoint references a Turn but is owned by the Feedback,
so the two cascades have to unwind in an order that does not trip the foreign key.
"""
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from backend.db.models import (
    AnalysisJob,
    Feedback,
    FeedbackPoint,
    Finding,
    Language,
    Measurement,
    MetricType,
    Persona,
    Scenario,
    Session,
    Turn,
)
from tests.conftest import ReferenceRows


@pytest.fixture
def session_with_full_subtree(db_session: DbSession, reference_data: ReferenceRows) -> Session:
    """One Session with every kind of child row hanging off it."""
    session = Session(
        subject_id="pseudonym-for-this-session",
        persona_id=reference_data.persona.persona_id,
        scenario_id=reference_data.scenario.scenario_id,
        language_code=reference_data.language.code,
        status="completed",
        started_at=datetime(2026, 8, 27, 10, 0, 0, tzinfo=UTC),
        ended_at=datetime(2026, 8, 27, 10, 5, 0, tzinfo=UTC),
    )
    db_session.add(session)
    db_session.flush()

    turn = Turn(
        session_id=session.session_id,
        seq_index=1,
        user_transcript="Was kostet das?",
        persona_transcript="Das hängt vom Umfang ab.",
        user_duration_ms=1500,
        persona_duration_ms=2200,
    )
    db_session.add(turn)
    db_session.flush()

    metric_type_id = reference_data.metric_type.metric_type_id
    finding = Finding(
        turn_id=turn.turn_id,
        metric_type_id=metric_type_id,
        category="speaking_rate",
        offset_ms=400,
        description="Zu schnell gesprochen.",
    )
    feedback = Feedback(
        session_id=session.session_id,
        summary="Insgesamt solide.",
        created_at=datetime(2026, 8, 27, 10, 6, 0, tzinfo=UTC),
    )
    db_session.add_all(
        [
            Measurement(turn_id=turn.turn_id, metric_type_id=metric_type_id, value=142.5),
            finding,
            feedback,
            AnalysisJob(
                session_id=session.session_id,
                kind="feedback",
                status="done",
                attempts=1,
                updated_at=datetime(2026, 8, 27, 10, 6, 0, tzinfo=UTC),
            ),
        ]
    )
    db_session.flush()

    # References a Turn but belongs to the Feedback — the ordering trap.
    db_session.add(
        FeedbackPoint(
            feedback_id=feedback.feedback_id,
            turn_id=turn.turn_id,
            finding_id=finding.finding_id,
            text="Sprich beim Preis langsamer.",
        )
    )
    db_session.commit()
    return session


def _count(db: DbSession, model: type) -> int:
    return db.query(model).count()


@pytest.mark.usefixtures("session_with_full_subtree")
def test_subtree_is_set_up_as_expected(db_session: DbSession) -> None:
    """Guards the fixture itself: without every child row present, the delete
    tests below would pass for the wrong reason."""
    assert _count(db_session, Turn) == 1
    assert _count(db_session, Measurement) == 1
    assert _count(db_session, Finding) == 1
    assert _count(db_session, Feedback) == 1
    assert _count(db_session, FeedbackPoint) == 1
    assert _count(db_session, AnalysisJob) == 1


def test_deleting_a_session_removes_its_whole_subtree(
    db_session: DbSession, session_with_full_subtree: Session
) -> None:
    """One delete has to clear the Session and everything owned by it."""
    db_session.delete(session_with_full_subtree)
    db_session.commit()

    assert _count(db_session, Session) == 0
    assert _count(db_session, Turn) == 0
    assert _count(db_session, Measurement) == 0
    assert _count(db_session, Finding) == 0
    assert _count(db_session, Feedback) == 0
    assert _count(db_session, FeedbackPoint) == 0
    assert _count(db_session, AnalysisJob) == 0


def test_deleting_a_session_leaves_the_reference_data_alone(
    db_session: DbSession, session_with_full_subtree: Session
) -> None:
    """Personas, Scenarios, Languages and MetricTypes are shared across Sessions;
    deleting one User's data must not take another's options with it."""
    db_session.delete(session_with_full_subtree)
    db_session.commit()

    assert _count(db_session, Persona) == 1
    assert _count(db_session, Scenario) == 1
    assert _count(db_session, Language) == 1
    assert _count(db_session, MetricType) == 1


@pytest.mark.usefixtures("session_with_full_subtree")
def test_raw_sql_delete_also_clears_the_subtree(db_session: DbSession) -> None:
    """The ORM cascade is not the only path any more: the foreign keys carry
    ON DELETE, so a plain DELETE — a retention job, a manual fix, a
    self-service deletion written in SQL — cannot fail on a constraint or leave
    orphans behind."""
    db_session.execute(text("DELETE FROM session"))
    db_session.commit()

    assert _count(db_session, Turn) == 0
    assert _count(db_session, Measurement) == 0
    assert _count(db_session, Finding) == 0
    assert _count(db_session, Feedback) == 0
    assert _count(db_session, FeedbackPoint) == 0
    assert _count(db_session, AnalysisJob) == 0


@pytest.mark.usefixtures("session_with_full_subtree")
def test_a_persona_with_sessions_cannot_be_deleted(db_session: DbSession) -> None:
    """Reference tables deliberately do *not* cascade: removing a Persona must
    fail loudly rather than silently taking every Session it ever ran with."""
    with pytest.raises(IntegrityError):
        db_session.execute(text("DELETE FROM persona"))
        db_session.commit()
    db_session.rollback()
