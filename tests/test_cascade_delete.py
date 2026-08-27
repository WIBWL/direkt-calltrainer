"""Deleting a Session must take its whole subtree with it and leave the shared
reference data alone.

This is the mechanism behind ADR 0034's promise that a User can delete their own
data. The cascades are declared at ORM level only (`cascade="all, delete-orphan"`)
— the foreign keys carry no `ON DELETE`, so this works through the ORM and not
through raw SQL. That distinction is exactly what these tests pin down, including
the awkward case: a Feedbackpunkt references a Turn but is owned by the Feedback,
so the two cascades have to unwind in an order that does not trip the foreign key.
"""
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session as DbSession

from backend.db.models import (
    AnalysisJob,
    Befund,
    Feedback,
    Feedbackpunkt,
    Messung,
    MetrikTyp,
    Persona,
    Session,
    Sprache,
    Szenario,
    Turn,
)
from tests.conftest import ReferenceRows


@pytest.fixture
def session_with_full_subtree(db_session: DbSession, reference_data: ReferenceRows) -> Session:
    """One Session with every kind of child row hanging off it."""
    session = Session(
        subject_id="pseudonym-for-this-session",
        persona_id=reference_data.persona.persona_id,
        szenario_id=reference_data.szenario.szenario_id,
        sprache_code=reference_data.sprache.sprache_code,
        status="beendet",
        gestartet_am=datetime(2026, 8, 27, 10, 0, 0, tzinfo=UTC),
        beendet_am=datetime(2026, 8, 27, 10, 5, 0, tzinfo=UTC),
    )
    db_session.add(session)
    db_session.flush()

    turn = Turn(
        session_id=session.session_id,
        seq_index=1,
        nutzer_transkript="Was kostet das?",
        persona_transkript="Das hängt vom Umfang ab.",
        nutzer_dauer_ms=1500,
        persona_dauer_ms=2200,
    )
    db_session.add(turn)
    db_session.flush()

    metrik_typ_id = reference_data.metrik_typ.metrik_typ_id
    befund = Befund(
        turn_id=turn.turn_id,
        metrik_typ_id=metrik_typ_id,
        kategorie="tempo",
        offset_ms=400,
        beschreibung="Zu schnell gesprochen.",
    )
    feedback = Feedback(
        session_id=session.session_id,
        zusammenfassung="Insgesamt solide.",
        erstellt_am=datetime(2026, 8, 27, 10, 6, 0, tzinfo=UTC),
    )
    db_session.add_all(
        [
            Messung(turn_id=turn.turn_id, metrik_typ_id=metrik_typ_id, wert=142.5),
            befund,
            feedback,
            AnalysisJob(
                session_id=session.session_id,
                art="feedback",
                status="done",
                versuche=1,
                aktualisiert_am=datetime(2026, 8, 27, 10, 6, 0, tzinfo=UTC),
            ),
        ]
    )
    db_session.flush()

    # References a Turn but belongs to the Feedback — the ordering trap.
    db_session.add(
        Feedbackpunkt(
            feedback_id=feedback.feedback_id,
            turn_id=turn.turn_id,
            befund_id=befund.befund_id,
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
    assert _count(db_session, Messung) == 1
    assert _count(db_session, Befund) == 1
    assert _count(db_session, Feedback) == 1
    assert _count(db_session, Feedbackpunkt) == 1
    assert _count(db_session, AnalysisJob) == 1


def test_deleting_a_session_removes_its_whole_subtree(
    db_session: DbSession, session_with_full_subtree: Session
) -> None:
    """One delete has to clear the Session and everything owned by it."""
    db_session.delete(session_with_full_subtree)
    db_session.commit()

    assert _count(db_session, Session) == 0
    assert _count(db_session, Turn) == 0
    assert _count(db_session, Messung) == 0
    assert _count(db_session, Befund) == 0
    assert _count(db_session, Feedback) == 0
    assert _count(db_session, Feedbackpunkt) == 0
    assert _count(db_session, AnalysisJob) == 0


def test_deleting_a_session_leaves_the_reference_data_alone(
    db_session: DbSession, session_with_full_subtree: Session
) -> None:
    """Personas, Szenarien, Sprachen and MetrikTypen are shared across Sessions;
    deleting one User's data must not take another's options with it."""
    db_session.delete(session_with_full_subtree)
    db_session.commit()

    assert _count(db_session, Persona) == 1
    assert _count(db_session, Szenario) == 1
    assert _count(db_session, Sprache) == 1
    assert _count(db_session, MetrikTyp) == 1
