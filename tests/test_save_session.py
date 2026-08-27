"""The write path from ADR 0034: a finished Session becomes exactly one row,
with its Turns, in one transaction.

These tests exercise `repository.save_session` directly rather than through the
WebSocket, because the interesting behaviour is the mapping — in-memory Turns to
paired rows, end reason to `session.status` — not the transport.
"""
import uuid

import pytest
from sqlalchemy.orm import Session as DbSession

from backend.db import repository
from backend.db.models import Persona, Session
from backend.db.models import Turn as TurnRow
from backend.session.models import Turn
from tests.conftest import SESSION_ENDED, SESSION_STARTED, make_finished_session

# Every test here needs the Persona/Szenario a Session points at, but none of
# them look at the fixture's return value.
pytestmark = pytest.mark.usefixtures("reference_data")


def _default_turns() -> list[Turn]:
    return [
        Turn(seq=1, persona_text="Guten Tag, Brandt hier.", persona_duration_ms=1800),
        Turn(
            seq=2,
            user_text="Wie kann ich helfen?",
            persona_text="Mir ist das zu teuer.",
            user_duration_ms=1200,
            persona_duration_ms=2400,
        ),
    ]


def _save(db: DbSession, *, reason: str = "user", turns: list[Turn] | None = None) -> int:
    finished = make_finished_session(
        reason=reason, turns=_default_turns() if turns is None else turns
    )
    session_id = repository.save_session(db, finished)
    db.commit()
    return session_id


def test_saves_the_session_and_its_turns(db_session: DbSession) -> None:
    """The happy path: one Session row, both Turns, timestamps preserved."""
    _save(db_session)

    session = db_session.query(Session).one()
    assert session.status == "beendet"
    assert session.gestartet_am == SESSION_STARTED
    assert session.beendet_am == SESSION_ENDED
    assert db_session.query(TurnRow).count() == 2


def test_assigns_a_public_id_distinct_from_the_primary_key(db_session: DbSession) -> None:
    """The client never sees session_id — the wire carries extern_id, so a
    sequential primary key cannot be used to guess at other Sessions."""
    _save(db_session)

    session = db_session.query(Session).one()
    assert isinstance(session.extern_id, uuid.UUID)
    assert str(session.extern_id) != str(session.session_id)


def test_opening_turn_is_stored_with_an_empty_user_half(db_session: DbSession) -> None:
    """The Persona speaks first, so Turn 1 has no user utterance — the paired
    Turn model represents that as an empty half, not as a missing row."""
    _save(db_session)

    opening = db_session.query(TurnRow).filter(TurnRow.seq_index == 1).one()
    assert opening.nutzer_transkript == ""
    assert opening.persona_transkript == "Guten Tag, Brandt hier."
    assert opening.nutzer_dauer_ms is None
    assert opening.persona_dauer_ms == 1800


def test_turns_keep_both_halves_and_their_durations(db_session: DbSession) -> None:
    """A regular Turn stores what both speakers said and how long each took."""
    _save(db_session)

    second = db_session.query(TurnRow).filter(TurnRow.seq_index == 2).one()
    assert second.nutzer_transkript == "Wie kann ich helfen?"
    assert second.persona_transkript == "Mir ist das zu teuer."
    assert second.nutzer_dauer_ms == 1200
    assert second.persona_dauer_ms == 2400


def test_missing_durations_are_stored_as_null(db_session: DbSession) -> None:
    """A client that does not send duration_ms yet must not cost us the Turn."""
    _save(db_session, turns=[Turn(seq=1, user_text="Hallo", persona_text="Guten Tag")])

    turn = db_session.query(TurnRow).one()
    assert turn.nutzer_dauer_ms is None
    assert turn.persona_dauer_ms is None


@pytest.mark.parametrize(
    ("reason", "expected"),
    [("user", "beendet"), ("completed", "beendet"), ("error", "abgebrochen")],
)
def test_end_reason_maps_onto_the_status_vocabulary(
    db_session: DbSession, reason: str, expected: str
) -> None:
    """"laufend" never occurs, because the row is written after the fact."""
    _save(db_session, reason=reason)

    assert db_session.query(Session).one().status == expected


def test_turns_without_any_text_are_skipped(db_session: DbSession) -> None:
    """A Turn whose legs all failed carries no transcript; the Session's
    "abgebrochen" status already records that it went wrong."""
    _save(
        db_session,
        reason="error",
        turns=[Turn(seq=1, persona_text="Guten Tag"), Turn(seq=2)],
    )

    assert db_session.query(TurnRow).count() == 1


def test_unknown_persona_is_refused_rather_than_written_partially(db_session: DbSession) -> None:
    """A bad key must not leave a Session row behind without its Turns."""
    with pytest.raises(LookupError):
        repository.save_session(
            db_session, make_finished_session(persona_key="does-not-exist")
        )
    db_session.rollback()
    assert db_session.query(Session).count() == 0


def test_a_deactivated_persona_can_still_receive_a_session(db_session: DbSession) -> None:
    """A Persona retired while a call was running must not make that call
    unrecordable — unlike the lookup used when starting one."""
    db_session.query(Persona).update({"aktiv": False})
    db_session.commit()

    _save(db_session)

    assert db_session.query(Session).count() == 1
