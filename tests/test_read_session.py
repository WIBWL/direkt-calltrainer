"""Reading a stored Session back, so a Transcript survives a page reload.

The point of storing a Session at all (ADR 0034, F-12) is that it can be looked
at afterwards. These tests cover the round trip: write through
`save_session`, read through `find_session`, and get the same conversation back.
"""
import uuid
import pytest
from sqlalchemy.orm import Session as DbSession

from backend.db import repository
from backend.session.models import Turn
from tests.conftest import SESSION_ENDED, SESSION_STARTED, make_finished_session

pytestmark = pytest.mark.usefixtures("reference_data")


def _store(db: DbSession, extern_id: uuid.UUID) -> None:
    repository.save_session(
        db,
        make_finished_session(
            extern_id=extern_id,
            turns=[
                Turn(seq=1, persona_text="Guten Tag, Brandt hier.", persona_duration_ms=1800),
                Turn(
                    seq=2,
                    user_text="Was kann ich für Sie tun?",
                    persona_text="Mir ist das zu teuer.",
                    user_duration_ms=1200,
                    persona_duration_ms=2400,
                ),
            ],
        ),
    )
    db.commit()


def test_reads_back_what_was_written(db_session: DbSession) -> None:
    """The whole point of persisting: the same conversation comes back out."""
    extern_id = uuid.uuid4()
    _store(db_session, extern_id)

    stored = repository.find_session(db_session, extern_id)

    assert stored is not None
    assert stored.extern_id == extern_id
    assert stored.status == "beendet"
    assert stored.started_at == SESSION_STARTED
    assert stored.ended_at == SESSION_ENDED
    assert len(stored.turns) == 2


def test_turns_come_back_in_conversation_order(db_session: DbSession) -> None:
    """seq_index carries the ordering, so the read path has to sort by it."""
    extern_id = uuid.uuid4()
    _store(db_session, extern_id)

    stored = repository.find_session(db_session, extern_id)

    assert [turn.seq for turn in stored.turns] == [1, 2]
    assert stored.turns[0].persona_text == "Guten Tag, Brandt hier."
    assert stored.turns[1].user_text == "Was kann ich für Sie tun?"


def test_both_halves_and_durations_survive_the_round_trip(db_session: DbSession) -> None:
    """A Turn read back has to be indistinguishable from the one written."""
    extern_id = uuid.uuid4()
    _store(db_session, extern_id)

    second = repository.find_session(db_session, extern_id).turns[1]
    assert second.user_text == "Was kann ich für Sie tun?"
    assert second.persona_text == "Mir ist das zu teuer."
    assert second.user_duration_ms == 1200
    assert second.persona_duration_ms == 2400


def test_persona_and_scenario_come_back_by_display_name(db_session: DbSession) -> None:
    """The post-call view shows names, not the internal keys."""
    extern_id = uuid.uuid4()
    _store(db_session, extern_id)

    stored = repository.find_session(db_session, extern_id)

    assert stored.persona_name == "Thomas Brandt"
    assert stored.scenario_name == "Kündigungsabsicht"


def test_unknown_id_is_not_found_rather_than_an_error(db_session: DbSession) -> None:
    """A stale id in a client's storage must produce a clean 404, not a crash."""
    assert repository.find_session(db_session, uuid.uuid4()) is None


def test_a_session_cannot_be_reached_through_its_primary_key(db_session: DbSession) -> None:
    """Only the public id opens a Session — the sequential primary key must not
    be usable as a lookup, or Sessions could be enumerated."""
    extern_id = uuid.uuid4()
    _store(db_session, extern_id)

    # The first Session has primary key 1; that value as a UUID finds nothing.
    as_uuid_of_pk = uuid.UUID(int=1)
    assert repository.find_session(db_session, as_uuid_of_pk) is None
