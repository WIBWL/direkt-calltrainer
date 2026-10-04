"""ADR 0114's backfill: a call stored with the VAD's padding in its figures,
corrected from what was stored. Runs the script's own `backfill` against a
throwaway database, the rows written through the real write path and then put
back into the shape the live path gave them before ADR 0114."""

from decimal import Decimal

import pytest
from sqlalchemy.orm import Session as DbSession

from shared.db import models as db_models
from shared.db.models import Measurement, MetricType, Session
from shared.feedback.acoustics import Pause
from shared.turn import Turn
from backend.scripts import backfill_voiced_span
from backend.tests.conftest import persist

# `app_database` is taken only to activate the fixture.
# pylint: disable=unused-argument,redefined-outer-name

pytestmark = pytest.mark.usefixtures("reference_data")

# `reference_data` seeds `pace` alone; the backfill reads and writes these too.
_KEYS = ("talk_share", "phonation_share", "pauses", "word_count", "reaction_time")

# One user recording as the client sent it: 0.8 s of VAD lead-in, 2 s from
# first sound to last (1.5 s of speech around a 0.5 s pause), 1 s of trailing
# silence -- 3.8 s in all, of which the old figures counted every millisecond.
_RECORDING_MS = 3_800
_PHONATION_MS = 1_500
_PAUSE_MS = 500
# The loudness curve at 100 ms: eight silent samples of lead-in, then sound.
_LOUDNESS = [None] * 8 + [60.0] * 20 + [None] * 10


@pytest.fixture
def inventory(db_session: DbSession) -> None:
    """The metric rows beyond `pace`, so the write path stores their figures."""
    db_session.add_all([
        MetricType(key=key, name=key, unit=None, aspect=db_models.ASPECT_HOW,
                   feature_id="F-00", active=True)
        for key in _KEYS
    ])
    db_session.commit()


def _user(seq: int, start: int, persona_start: int, loudness=None) -> Turn:
    """An exchange whose user side is placed where the old path placed it: at
    the start of the recording, padding included."""
    return Turn(
        seq=seq,
        user_text="Das ist meine Antwort auf Ihre Frage von eben.",
        user_offset_ms=start,
        user_end_ms=start + _RECORDING_MS,
        user_speech_ms=_RECORDING_MS,
        user_phonation_ms=_PHONATION_MS,
        pauses=[Pause(offset_ms=start + 1_500, duration_ms=_PAUSE_MS)],
        loudness_db=list(_LOUDNESS if loudness is None else loudness),
        persona_text="Verstanden, weiter.",
        persona_offset_ms=persona_start,
        persona_end_ms=persona_start + 2_000,
    )


def _call(loudness=None) -> list[Turn]:
    """The Persona opens (0-1 s), then two exchanges. Persona audio 5 s."""
    return [
        Turn(seq=1, persona_text="Guten Tag.", persona_offset_ms=0, persona_end_ms=1_000),
        _user(2, 1_000, 5_200, loudness),
        _user(3, 7_300, 11_500, loudness),
    ]


def _figures(db: DbSession) -> dict[str, Measurement]:
    db.expire_all()
    return {
        m.metric_type.key: m
        for m in db.query(Measurement).filter_by(segment=db_models.SEGMENT_CALL)
    }


def _as_stored_before_adr_0114(db: DbSession) -> None:
    """Put the three figures back the way the live path wrote them: the talk
    share over the recordings' length, the Redefluss with `speech_ms`, the
    reaction time without saying what its gaps end at."""
    found = _figures(db)
    user_ms, persona_ms = 2 * _RECORDING_MS, 5_000
    found["talk_share"].value = Decimal(user_ms * 100 / (user_ms + persona_ms)).quantize(Decimal("0.0001"))
    found["talk_share"].detail_json = {"user_ms": user_ms, "persona_ms": persona_ms}
    found["phonation_share"].value = Decimal(2 * _PHONATION_MS * 100 / user_ms).quantize(Decimal("0.0001"))
    found["phonation_share"].detail_json = {"speech_ms": user_ms, "phonation_ms": 2 * _PHONATION_MS}
    detail = dict(found["reaction_time"].detail_json)
    del detail["measured_to"]
    found["reaction_time"].detail_json = detail
    db.commit()


def test_the_talk_share_is_recomputed_over_the_voiced_span(
    db_session: DbSession, app_database: str, inventory: None
) -> None:
    """2 x (1.5 s + 0.5 s) of user against 5 s of Persona: 44.4 %, where the
    padded recordings made it 60.3 %."""
    persist(turns=_call())
    _as_stored_before_adr_0114(db_session)

    backfill_voiced_span.backfill(apply=True)

    talk = _figures(db_session)["talk_share"]
    assert float(talk.value) == pytest.approx(4_000 * 100 / 9_000, abs=1e-3)
    assert talk.detail_json["user_ms"] == 4_000
    assert talk.detail_json["backfilled"] is True


def test_the_redefluss_is_recomputed_over_the_voiced_span(
    db_session: DbSession, app_database: str, inventory: None
) -> None:
    """3 s of speech in 4 s from first sound to last, not in 7.6 s of recording."""
    persist(turns=_call())
    _as_stored_before_adr_0114(db_session)

    backfill_voiced_span.backfill(apply=True)

    flow = _figures(db_session)["phonation_share"]
    assert float(flow.value) == 75.0
    assert flow.detail_json["voiced_ms"] == 4_000
    assert "speech_ms" not in flow.detail_json


def test_the_reaction_time_is_moved_to_the_estimated_first_sound(
    db_session: DbSession, app_database: str, inventory: None
) -> None:
    """Eight silent samples put the first sound at 0.75 s into each recording
    (the middle of the step it was first heard in), so the gaps grow from 0
    and 0.1 s to 0.75 and 0.85 s. `at_ms` stays on the transcript's offsets,
    which is how the page finds the reply."""
    persist(turns=_call())
    _as_stored_before_adr_0114(db_session)

    backfill_voiced_span.backfill(apply=True)

    reaction = _figures(db_session)["reaction_time"]
    assert float(reaction.value) == pytest.approx(0.8)
    assert reaction.detail_json["gaps"] == [
        {"at_ms": 1_000, "duration_ms": 750},
        {"at_ms": 7_300, "duration_ms": 850},
    ]
    assert reaction.detail_json["measured_to"] == "first_sound"
    assert reaction.detail_json["first_sound_estimated"] is True


def test_a_second_run_changes_nothing(
    db_session: DbSession, app_database: str, inventory: None
) -> None:
    """Idempotent, as every backfill here is -- and for the reaction time that
    is not a courtesy: a second shift would move each reply by the padding again."""
    persist(turns=_call())
    _as_stored_before_adr_0114(db_session)
    backfill_voiced_span.backfill(apply=True)

    assert backfill_voiced_span.backfill(apply=True) == 0


def test_a_call_stored_after_adr_0114_is_left_alone(
    db_session: DbSession, app_database: str, inventory: None
) -> None:
    """The live path's own figures already agree with what the script would write."""
    persist(turns=_call())

    assert backfill_voiced_span.backfill(apply=True) == 0


def test_a_dry_run_writes_nothing(
    db_session: DbSession, app_database: str, inventory: None
) -> None:
    """Without `--apply` the run reports the Session and leaves every figure."""
    persist(turns=_call())
    _as_stored_before_adr_0114(db_session)
    before = {key: float(m.value) for key, m in _figures(db_session).items()}

    assert backfill_voiced_span.backfill(apply=False) == 1

    assert {key: float(m.value) for key, m in _figures(db_session).items()} == before


def test_a_talk_share_over_a_recording_without_silence_is_removed(
    db_session: DbSession, app_database: str, inventory: None
) -> None:
    """ADR 0085: over a noise floor the span is the whole recording again, so
    the live path now withholds the figure, and a stored one is as wrong as it
    was. Words were counted and no Sprechtempo stored: that is the call."""
    persist(turns=_call(loudness=[60.0] * 38))
    session_id = db_session.query(Session).one().session_id
    talk_id = db_session.query(MetricType).filter_by(key="talk_share").one().metric_type_id
    db_session.add(Measurement(
        session_id=session_id, metric_type_id=talk_id, value=Decimal("60.3175"),
        detail_json={"user_ms": 7_600, "persona_ms": 5_000}, segment=db_models.SEGMENT_CALL,
    ))
    db_session.commit()

    backfill_voiced_span.backfill(apply=True)

    assert "talk_share" not in _figures(db_session)
