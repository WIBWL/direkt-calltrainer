"""The persistence schema (SQLAlchemy models), and what the database enforces.

Covers:
  ADR 0026  normalized schema for session persistence
  ADR 0025  SQLAlchemy ORM as the single source of truth
  ADR 0026  metric types carry a `feature_id` linking a measurement back to
            a feature in docs/features.md (F-24, F-35..F-38, F-51, ...)
  ADR 0029  measurement detail is JSONB
  ADR 0051  one set of statistics per Session, not per Turn
  ADR 0053  invariants the code assumes are enforced by the database
  F-09/F-14  Feedback row: qualitative summary (NOT NULL) + optional score
  F-12      Turn transcripts are stored

Two halves. The first asserts against the mapper metadata and needs no
infrastructure. The second, below, writes to a real database, because a
constraint that is only declared is not the same as one the server applies --
and these particular constraints exist to catch a writer that the tests above
cannot see.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import Numeric, inspect
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError

from backend.db import models
from backend.db.base import Base

# pylint: disable=missing-function-docstring


def test_every_domain_table_is_present():
    expected = {
        "persona", "persona_objection", "scenario", "language", "metric_type",
        "session", "turn", "measurement", "finding", "feedback", "feedback_point",
        "analysis_job",
    }
    assert expected <= set(Base.metadata.tables)


def test_session_owns_its_turns_with_a_delete_cascade():
    """ADR 0026: deleting a Session takes its whole subtree with it."""
    rel = inspect(models.Session).relationships["turns"]
    assert rel.cascade.delete
    assert "session_id" in {c.name for c in models.Turn.__table__.columns}


def test_turn_stores_a_transcript_and_a_speaker():
    """F-12: the transcript text of each utterance is persisted."""
    cols = {c.name: c for c in models.Turn.__table__.columns}
    assert "transcript" in cols
    assert "speaker" in cols  # user | persona


def test_feedback_summary_is_mandatory_and_score_is_optional():
    """F-09/F-14: a qualitative summary is required; the numeric score is not."""
    cols = {c.name: c for c in models.Feedback.__table__.columns}
    assert cols["summary"].nullable is False
    assert cols["score"].nullable is True
    assert models.Feedback.__table__.c.session_id.unique  # one feedback per session


def test_metric_type_links_a_measurement_to_a_feature():
    """ADR 0030: `feature_id` on metrik_typ is how a stored measurement is
    traced back to a functional requirement in docs/features.md."""
    cols = {c.name for c in models.MetricType.__table__.columns}
    assert "feature_id" in cols
    assert "key" in cols  # e.g. 'talk_share', 'pace'


def test_measurement_detail_is_jsonb():
    """ADR 0029: a metric's course over the call is stored as JSONB."""
    assert isinstance(models.Measurement.__table__.c.detail_json.type, JSONB)


def test_analysis_job_has_a_persisted_status_and_retry_count():
    """ADR 0032: job outcome/status is persisted (queued|running|done|failed)."""
    cols = {c.name for c in models.AnalysisJob.__table__.columns}
    assert {"status", "attempts", "error_text"} <= cols


def test_reference_entities_are_keyed_by_a_stable_business_key():
    for model in (models.Persona, models.Scenario, models.MetricType):
        assert model.__table__.c.key.unique


def test_measurement_value_is_numeric():
    assert isinstance(models.Measurement.__table__.c.value.type, Numeric)


# --- what the database enforces -----------------------------------------
#
# The migration a7c39e5f21b8 turned two invariants that lived in a docstring
# into constraints. These pin the behaviour rather than the declaration, so a
# later migration cannot drop them unnoticed.


def _session(reference_data) -> models.Session:
    return models.Session(
        subject_id="pseudonym",
        persona_id=reference_data.persona.persona_id,
        scenario_id=reference_data.scenario.scenario_id,
        language_code=reference_data.language.code,
        status=models.STATUS_COMPLETED,
        started_at=datetime(2026, 9, 5, 10, 0, tzinfo=UTC),
        ended_at=datetime(2026, 9, 5, 10, 5, tzinfo=UTC),
    )


def test_one_measurement_per_metric_and_session(db_session, reference_data) -> None:
    """ADR 0051: one set of statistics per Session. A second speaking rate for
    the same call would be rendered next to the first, with nothing to say
    which one holds."""
    session = _session(reference_data)
    db_session.add(session)
    db_session.flush()
    for _ in range(2):
        db_session.add(models.Measurement(
            session_id=session.session_id,
            metric_type_id=reference_data.metric_type.metric_type_id,
            value=Decimal("1.0"),
        ))

    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_one_turn_per_position_in_a_session(db_session, reference_data) -> None:
    """api/sessions.py orders the transcript by seq_index alone, so a duplicate
    would leave the order of those two lines to the server -- and differently
    on each read."""
    session = _session(reference_data)
    db_session.add(session)
    db_session.flush()
    for speaker in (models.SPEAKER_USER, models.SPEAKER_PERSONA):
        db_session.add(models.Turn(
            session_id=session.session_id,
            speaker=speaker,
            seq_index=0,
            start_offset_ms=0,
            transcript="dieselbe Position",
        ))

    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()
