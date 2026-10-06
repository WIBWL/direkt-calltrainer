"""Metrics over the demanding stretches and the rest (F-62, ADR 0081)."""

import asyncio
import json

import httpx
import pytest
from sqlalchemy.orm import Session as DbSession

from shared.clients import llm
from shared.db import models as db_models
from shared.db.models import Measurement, Session, Turn as TurnRow
from shared.feedback.segments import SEGMENT_METRIC_KEYS
from shared.turn import Turn
from shared.tests.fixtures import METRIC_KEY
from backend.tests.conftest import persist
from worker import segments
from worker.generator import generate_feedback

# `app_database` is taken by several tests only to activate the fixture.
# pylint: disable=unused-argument

pytestmark = pytest.mark.usefixtures("reference_data")

# Enough exchanges for both stretches to clear `MIN_UTTERANCES`.
_EXCHANGES = 8

# Two silent frames, or `_silence_found` withholds the silence-based figures.
_LOUDNESS = (62.0, 64.5, None, 61.0, 66.0, 63.5, None, 62.5)


def _call(pressing: set[int]) -> list[Turn]:
    """A call of `_EXCHANGES` exchanges; `pressing` holds the 1-based indices
    whose Persona line pushes back."""
    turns = []
    for index in range(1, _EXCHANGES + 1):
        start = (index - 1) * 10_000
        turns.append(Turn(
            seq=index,
            user_text=f"Antwort {index} auf die Frage nach dem Termin.",
            user_offset_ms=start,
            user_end_ms=start + 3_000,
            user_speech_ms=3_000,
            user_phonation_ms=2_400,
            loudness_db=list(_LOUDNESS),
            persona_text=(
                "Das reicht mir so nicht." if index in pressing else "Gut, verstanden."
            ),
            persona_offset_ms=start + 4_000,
            persona_end_ms=start + 6_000,
        ))
    return turns


def _stub_model(monkeypatch: pytest.MonkeyPatch, reply: str) -> None:
    async def complete(messages: list[dict[str, str]], *,
                       max_tokens: int | None = None, think: bool = False) -> str:
        return reply

    monkeypatch.setattr(llm, "complete", complete)


def _reply(pressure_turns: list[int]) -> str:
    return json.dumps({
        "summary": "Sachliches Gespräch.",
        "pressure_turns": pressure_turns,
        "strengths": [],
        "improvements": [],
    })


def _persona_turn_ids(db: DbSession) -> list[int]:
    """The stored Persona utterances, in the order they were spoken."""
    return [
        row.turn_id
        for row in db.query(TurnRow).order_by(TurnRow.seq_index)
        if row.speaker == db_models.SPEAKER_PERSONA
    ]


def _segment_values(db: DbSession, segment: str) -> dict[str, float]:
    db.expire_all()
    return {
        m.metric_type.key: float(m.value)
        for m in db.query(Measurement).filter_by(segment=segment)
    }


def test_a_user_utterance_keeps_its_raw_facts(
    db_session: DbSession, app_database: str
) -> None:
    persist(turns=_call(pressing=set()))

    rows = db_session.query(TurnRow).filter_by(speaker=db_models.SPEAKER_USER).all()

    assert rows
    for row in rows:
        assert row.acoustics_json["phonation_ms"] == 2_400
        assert row.acoustics_json["loudness_db"] == list(_LOUDNESS)


def test_a_persona_utterance_carries_no_facts(
    db_session: DbSession, app_database: str
) -> None:
    persist(turns=_call(pressing=set()))

    rows = db_session.query(TurnRow).filter_by(speaker=db_models.SPEAKER_PERSONA).all()

    assert rows
    assert all(row.acoustics_json is None for row in rows)


def test_an_unmeasured_utterance_stores_no_facts(
    db_session: DbSession, app_database: str
) -> None:
    persist(turns=[Turn(
        seq=1, user_text="Guten Tag.", user_offset_ms=0, user_end_ms=1_000,
        persona_text="Brandt.", persona_offset_ms=1_500, persona_end_ms=2_500,
    )])

    row = db_session.query(TurnRow).filter_by(speaker=db_models.SPEAKER_USER).one()

    assert row.acoustics_json is None


def test_the_marked_exchanges_become_their_own_measurements(
    db_session: DbSession, app_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    persist(turns=_call(pressing={1, 2, 3, 4}))
    session_id = db_session.query(Session).one().session_id
    pressing = _persona_turn_ids(db_session)[:4]
    _stub_model(monkeypatch, _reply(pressing))

    generate_feedback(session_id)

    # Only `METRIC_KEY` is seeded, and unknown metrics are dropped (as `_write_analysis`
    # does), so assert that one came out for both stretches; the key set is pinned below.
    assert METRIC_KEY in _segment_values(db_session, db_models.SEGMENT_PRESSURE)
    assert METRIC_KEY in _segment_values(db_session, db_models.SEGMENT_REST)


def test_the_segment_metrics_are_the_ones_that_stay_defined_on_a_part() -> None:
    assert set(SEGMENT_METRIC_KEYS) == {
        "talk_share", "pace", "pauses", "run_length", "loudness",
    }
    assert "reaction_time" not in SEGMENT_METRIC_KEYS
    assert "questions" not in SEGMENT_METRIC_KEYS
    assert "word_count" not in SEGMENT_METRIC_KEYS
    assert "intonation" not in SEGMENT_METRIC_KEYS


def test_the_two_stretches_are_measured_apart(
    db_session: DbSession, app_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    turns = _call(pressing={1, 2, 3, 4})
    # The answers to those lines: the user utterance after the pressing line.
    for index in range(1, 5):
        turns[index].user_phonation_ms = 1_200  # same words, half the time
    persist(turns=turns)
    session_id = db_session.query(Session).one().session_id
    _stub_model(monkeypatch, _reply(_persona_turn_ids(db_session)[:4]))

    generate_feedback(session_id)

    under_pressure = _segment_values(db_session, db_models.SEGMENT_PRESSURE)[METRIC_KEY]
    otherwise = _segment_values(db_session, db_models.SEGMENT_REST)[METRIC_KEY]
    assert under_pressure == pytest.approx(otherwise * 2, rel=0.01)


def test_a_user_utterance_cannot_mark_a_stretch(
    db_session: DbSession, app_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    persist(turns=_call(pressing={1, 2, 3, 4}))
    session_id = db_session.query(Session).one().session_id
    user_ids = [
        row.turn_id for row in db_session.query(TurnRow)
        if row.speaker == db_models.SPEAKER_USER
    ]
    _stub_model(monkeypatch, _reply(user_ids))

    generate_feedback(session_id)

    assert _segment_values(db_session, db_models.SEGMENT_PRESSURE) == {}
    assert db_session.query(TurnRow).filter_by(pressed=True).count() == 0


def test_an_id_from_another_session_is_ignored(
    db_session: DbSession, app_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    persist(turns=_call(pressing=set()))
    other = db_session.query(Session).one().session_id
    foreign_ids = _persona_turn_ids(db_session)
    persist(turns=_call(pressing={1, 2, 3, 4}))
    session_id = [
        s.session_id for s in db_session.query(Session).all() if s.session_id != other
    ][0]
    _stub_model(monkeypatch, _reply(foreign_ids))

    generate_feedback(session_id)

    marked = db_session.query(TurnRow).filter_by(session_id=session_id, pressed=True)
    assert marked.count() == 0


def test_a_call_nobody_pushed_back_in_has_no_segments(
    db_session: DbSession, app_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    persist(turns=_call(pressing=set()))
    session_id = db_session.query(Session).one().session_id
    _stub_model(monkeypatch, _reply([]))

    generate_feedback(session_id)

    assert db_session.query(Measurement).filter(
        Measurement.segment != db_models.SEGMENT_CALL
    ).count() == 0


def test_a_stretch_too_short_to_describe_is_not_measured(
    db_session: DbSession, app_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    persist(turns=_call(pressing={1}))
    session_id = db_session.query(Session).one().session_id
    _stub_model(monkeypatch, _reply(_persona_turn_ids(db_session)[:1]))

    generate_feedback(session_id)

    assert _segment_values(db_session, db_models.SEGMENT_PRESSURE) == {}
    # Stored even alone; the interface decides one column says nothing.
    assert _segment_values(db_session, db_models.SEGMENT_REST) != {}


def test_the_answer_to_a_pressing_line_is_what_is_measured(
    db_session: DbSession, app_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    persist(turns=_call(pressing={1, 2, 3, 4}))
    session_id = db_session.query(Session).one().session_id
    _stub_model(monkeypatch, _reply(_persona_turn_ids(db_session)[:4]))

    generate_feedback(session_id)

    db_session.expire_all()
    rows = db_session.query(TurnRow).order_by(TurnRow.seq_index).all()
    pressed_answers = [
        # Within one exchange the user speaks first, so the answer to the line
        # at index i is the user row after it.
        rows[index + 1].transcript
        for index, row in enumerate(rows)
        if row.pressed and index + 1 < len(rows)
    ]
    assert pressed_answers == [f"Antwort {n} auf die Frage nach dem Termin." for n in (2, 3, 4, 5)]


def test_the_whole_call_figures_are_untouched(
    db_session: DbSession, app_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    persist(turns=_call(pressing={1, 2, 3, 4}))
    session_id = db_session.query(Session).one().session_id
    before = _segment_values(db_session, db_models.SEGMENT_CALL)
    _stub_model(monkeypatch, _reply(_persona_turn_ids(db_session)[:4]))

    generate_feedback(session_id)

    assert _segment_values(db_session, db_models.SEGMENT_CALL) == before


def test_regenerating_replaces_the_segments_rather_than_adding_to_them(
    db_session: DbSession, app_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    persist(turns=_call(pressing={1, 2, 3, 4}))
    session_id = db_session.query(Session).one().session_id
    persona_ids = _persona_turn_ids(db_session)
    _stub_model(monkeypatch, _reply(persona_ids[:4]))
    generate_feedback(session_id)

    _stub_model(monkeypatch, _reply(persona_ids[4:]))
    generate_feedback(session_id)

    pressure = db_session.query(Measurement).filter_by(
        segment=db_models.SEGMENT_PRESSURE
    ).all()
    assert len(pressure) == len({m.metric_type_id for m in pressure})
    assert db_session.query(TurnRow).filter_by(pressed=True).count() == len(persona_ids[4:])


def test_a_broken_segment_measurement_does_not_cost_the_wrap_up(
    db_session: DbSession, app_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    persist(turns=_call(pressing={1, 2, 3, 4}))
    session_id = db_session.query(Session).one().session_id
    _stub_model(monkeypatch, _reply(_persona_turn_ids(db_session)[:4]))
    monkeypatch.setattr(
        segments, "measure_segments",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    generate_feedback(session_id)

    db_session.expire_all()
    assert db_session.query(Session).one().feedback is not None
    assert _segment_values(db_session, db_models.SEGMENT_CALL) != {}


async def test_the_detail_route_keeps_the_two_lists_apart(
    api_client: httpx.AsyncClient, db_session: DbSession, app_database: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extern_id = persist(turns=_call(pressing={1, 2, 3, 4}))
    session_id = db_session.query(Session).one().session_id
    _stub_model(monkeypatch, _reply(_persona_turn_ids(db_session)[:4]))
    # In a thread: `generate_feedback` opens an event loop of its own, which it
    # cannot do inside this test's.
    await asyncio.to_thread(generate_feedback, session_id)

    body = (await api_client.get(f"/api/sessions/{extern_id}")).json()

    keys = [m["key"] for m in body["measurements"]]
    assert keys == sorted(set(keys))
    assert {s["segment"] for s in body["segments"]} == {"pressure", "rest"}
    # Figures only: a segment's loudness curve is a curve like any other, and
    # nothing plots it (ADR 0064's reason one level down).
    assert all("detail" not in s for s in body["segments"])


async def test_the_listing_carries_the_comparison_without_the_curves(
    api_client: httpx.AsyncClient, db_session: DbSession, app_database: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persist(turns=_call(pressing={1, 2, 3, 4}))
    session_id = db_session.query(Session).one().session_id
    _stub_model(monkeypatch, _reply(_persona_turn_ids(db_session)[:4]))
    await asyncio.to_thread(generate_feedback, session_id)

    row = (await api_client.get("/api/sessions")).json()["sessions"][0]

    assert {s["segment"] for s in row["segments"]} == {"pressure", "rest"}
    assert [m["key"] for m in row["measurements"]] == sorted(
        {m["key"] for m in row["measurements"]}
    )
