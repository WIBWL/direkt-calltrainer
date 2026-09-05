"""The write path from ADR 0034: a finished Session becomes exactly one row,
with its Turns, in one transaction.

These tests exercise `persistence.persist_session` directly rather than through
the WebSocket, because the interesting behaviour is the mapping — in-memory
Turns to utterance rows, end reason to `session.status` — not the transport.

A Turn is an exchange in memory but one row per speaker in the schema
(ADR 0026), so the counts below are utterances, not exchanges; `utterances()`
in backend/session/models.py is what performs that flattening.
"""
import uuid

import pytest
from sqlalchemy.orm import Session as DbSession

from backend.db.models import AnalysisJob, Persona, Session
from backend.session import persistence
from backend.db.models import Turn as TurnRow
from backend.session.models import Turn
from tests.conftest import SESSION_STARTED, persist

# Every test here needs the Persona/Scenario a Session points at, and the
# application engine pointed at the same throwaway database.
pytestmark = pytest.mark.usefixtures("app_database", "reference_data")


def _default_turns() -> list[Turn]:
    """Two exchanges: the Persona's opening line, then a full back-and-forth.

    Three utterances in total — the opening Turn has no user half.
    """
    return [
        Turn(
            seq=1,
            persona_text="Guten Tag, Brandt hier.",
            persona_offset_ms=0,
            persona_end_ms=1800,
        ),
        Turn(
            seq=2,
            user_text="Wie kann ich helfen?",
            user_offset_ms=2000,
            user_end_ms=3200,
            persona_text="Mir ist das zu teuer.",
            persona_offset_ms=3500,
            persona_end_ms=5900,
        ),
    ]


def test_saves_the_session_and_its_turns(db_session: DbSession) -> None:
    """The happy path: one Session row, every utterance, timestamps preserved."""
    persist(turns=_default_turns())

    session = db_session.query(Session).one()
    assert session.status == "completed"
    assert session.started_at == SESSION_STARTED
    assert session.ended_at is not None
    assert db_session.query(TurnRow).count() == 3


def test_assigns_a_public_id_distinct_from_the_primary_key(db_session: DbSession) -> None:
    """The client never sees session_id — the wire carries extern_id, so a
    sequential primary key cannot be used to guess at other Sessions."""
    extern_id = persist(turns=_default_turns())

    session = db_session.query(Session).one()
    assert isinstance(session.extern_id, uuid.UUID)
    assert session.extern_id == extern_id
    assert str(session.extern_id) != str(session.session_id)


def test_opening_turn_becomes_a_persona_row_only(db_session: DbSession) -> None:
    """The Persona speaks first, so the opening exchange has no user utterance
    — which is one row, not a row with an empty half."""
    persist(turns=_default_turns())

    first = db_session.query(TurnRow).order_by(TurnRow.seq_index).first()
    assert first.speaker == "persona"
    assert first.transcript == "Guten Tag, Brandt hier."
    assert first.start_offset_ms == 0
    assert first.duration_ms == 1800


def test_each_half_becomes_its_own_row_in_speaking_order(db_session: DbSession) -> None:
    """Within one exchange the user speaks first, then the Persona answers;
    seq_index carries that order across the whole Session."""
    persist(turns=_default_turns())

    rows = db_session.query(TurnRow).order_by(TurnRow.seq_index).all()
    assert [(r.speaker, r.transcript) for r in rows] == [
        ("persona", "Guten Tag, Brandt hier."),
        ("user", "Wie kann ich helfen?"),
        ("persona", "Mir ist das zu teuer."),
    ]
    assert [r.seq_index for r in rows] == [0, 1, 2]
    assert [r.duration_ms for r in rows] == [1800, 1200, 2400]


def test_unmeasured_durations_are_stored_as_null(db_session: DbSession) -> None:
    """An utterance whose end was never measured must not cost us the Turn;
    NULL says "not measured", which a 0 would not."""
    persist(turns=[Turn(seq=1, user_text="Hallo", persona_text="Guten Tag")])

    assert db_session.query(TurnRow).count() == 2
    assert all(r.duration_ms is None for r in db_session.query(TurnRow).all())


@pytest.mark.parametrize(
    ("reason", "expected"),
    [("user", "completed"), ("completed", "completed"), ("error", "aborted")],
)
def test_end_reason_maps_onto_the_status_vocabulary(
    db_session: DbSession, reason: str, expected: str
) -> None:
    """"running" never occurs, because the row is written after the fact."""
    persist(reason=reason, turns=_default_turns())

    assert db_session.query(Session).one().status == expected


def test_utterances_without_any_text_are_skipped(db_session: DbSession) -> None:
    """A Turn whose legs all failed carries no transcript; the Session's
    "aborted" status already records that it went wrong."""
    persist(reason="error", turns=[Turn(seq=1, persona_text="Guten Tag"), Turn(seq=2)])

    assert db_session.query(TurnRow).count() == 1


def test_unknown_persona_is_refused_rather_than_written_partially(
    db_session: DbSession,
) -> None:
    """A bad key must not leave a Session row behind without its Turns."""
    with pytest.raises(LookupError):
        persist(persona_key="does-not-exist", turns=_default_turns())

    assert db_session.query(Session).count() == 0
    assert db_session.query(TurnRow).count() == 0


def test_a_deactivated_persona_can_still_receive_a_session(db_session: DbSession) -> None:
    """A Persona retired while a call was running must not make that call
    unrecordable — unlike the lookup used when starting one."""
    db_session.query(Persona).update({"active": False})
    db_session.commit()

    persist(turns=_default_turns())

    assert db_session.query(Session).count() == 1


def test_stale_running_feedback_job_is_marked_failed(
    db_session: DbSession,
) -> None:
    persist(turns=_default_turns())

    job = db_session.query(AnalysisJob).one()
    job.status = "running"
    db_session.commit()

    count = persistence.fail_running_feedback_jobs(
        "worker restarted"
    )

    db_session.expire_all()
    job = db_session.query(AnalysisJob).one()

    assert count == 1
    assert job.status == "failed"
    assert job.error_text == "worker restarted"


def test_feedback_failure_marker_does_not_overwrite_done_job(
    db_session: DbSession,
) -> None:
    persist(turns=_default_turns())

    session = db_session.query(Session).one()
    job = db_session.query(AnalysisJob).one()
    job.status = "done"
    job.error_text = None
    db_session.commit()

    persistence.mark_feedback_job_failed(
        session.session_id,
        "late worker failure",
    )

    db_session.expire_all()
    job = db_session.query(AnalysisJob).one()

    assert job.status == "done"
    assert job.error_text is None
