"""Reading a stored Session back as the call it was (ADR 0051, ADR 0081).

`backend/feedback/stored.py` is the one reader every consumer of a stored
Session goes through -- the served shapes, the wrap-up's dossier, the segment
pass and the backfills. These pin the three rules each of them used to write
out for itself, plus the one the segment pass got wrong: a slice of a reverse is
folded as a reverse.

Transient ORM objects, never flushed, so no database is needed.
"""

# pylint: disable=missing-function-docstring

from backend.db import models as db_models
from backend.feedback import stored


def _turn(seq: int, speaker: str, text: str) -> db_models.Turn:
    return db_models.Turn(
        turn_id=seq + 100, seq_index=seq, speaker=speaker, transcript=text,
        start_offset_ms=seq * 1000, duration_ms=800,
    )


def _session(*, reverse: bool = False) -> db_models.Session:
    session = db_models.Session(language_code="de")
    session.scenario = db_models.Scenario(reverse=reverse)
    # Stored out of order on purpose: the load order depends on the server.
    session.turns = [
        _turn(2, db_models.SPEAKER_PERSONA, "Worum geht es?"),
        _turn(0, db_models.SPEAKER_PERSONA, "Guten Tag."),
        _turn(3, db_models.SPEAKER_USER, "Um die Rechnung."),
        _turn(1, db_models.SPEAKER_USER, "Hallo, hier ist Anna."),
    ]
    return session


def test_turns_come_back_in_the_order_they_were_said():
    assert [t.seq_index for t in stored.ordered_turns(_session())] == [0, 1, 2, 3]


def test_user_texts_are_the_users_lines_in_order():
    assert stored.user_texts(_session()) == ["Hallo, hier ist Anna.", "Um die Rechnung."]


def test_whole_call_leaves_the_segment_rows_out():
    session = _session()
    session.measurements = [
        db_models.Measurement(metric_type_id=1, value=1, segment=db_models.SEGMENT_CALL),
        db_models.Measurement(metric_type_id=1, value=2, segment=db_models.SEGMENT_PRESSURE),
        db_models.Measurement(metric_type_id=1, value=3, segment=db_models.SEGMENT_REST),
    ]
    assert [m.value for m in stored.whole_call(session)] == [1]


def test_exchanges_pair_each_rebuilt_turn_with_its_row():
    pairs = stored.exchanges(_session())
    assert [row.seq_index for _, row in pairs] == [0, 1, 2, 3]
    turn, _ = pairs[1]
    assert turn.user_text == "Hallo, hier ist Anna."
    assert turn.user_offset_ms == 1000 and turn.user_end_ms == 1800
    assert not turn.user_acoustics_complete, "no stored facts: the milliseconds are withheld"


def test_a_slice_of_a_reverse_is_folded_as_a_reverse():
    """The segment pass folded its slices without the casting, so a metric that
    reads who rang would have measured a reverse the ordinary way round."""
    session = _session(reverse=True)
    part = [turn for turn, _ in stored.exchanges(session)][:2]
    call = stored.conversation_of(session, part)
    assert call.reverse is True
    assert call.language_id == "de"
