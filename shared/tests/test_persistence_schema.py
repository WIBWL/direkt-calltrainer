"""Schema metadata and what the database enforces (ADR 0025, 0026, 0029, 0051, 0053)."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import Numeric, inspect
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError

from shared.db import models
from shared.db.base import Base

# pylint: disable=missing-function-docstring


def test_every_domain_table_is_present():
    expected = {
        "persona", "persona_objection", "scenario", "language", "metric_type",
        "session", "turn", "measurement", "finding", "feedback", "feedback_point",
        "analysis_job",
    }
    assert expected <= set(Base.metadata.tables)


def test_session_owns_its_turns_with_a_delete_cascade():
    rel = inspect(models.Session).relationships["turns"]
    assert rel.cascade.delete
    assert "session_id" in {c.name for c in models.Turn.__table__.columns}


def test_turn_stores_a_transcript_and_a_speaker():
    cols = {c.name: c for c in models.Turn.__table__.columns}
    assert "transcript" in cols
    assert "speaker" in cols  # user | persona


def test_feedback_summary_is_mandatory_and_score_is_optional():
    cols = {c.name: c for c in models.Feedback.__table__.columns}
    assert cols["summary"].nullable is False
    assert cols["score"].nullable is True
    assert models.Feedback.__table__.c.session_id.unique  # one feedback per session


def test_metric_type_links_a_measurement_to_a_feature():
    cols = {c.name for c in models.MetricType.__table__.columns}
    assert "feature_id" in cols
    assert "key" in cols  # e.g. 'talk_share', 'pace'


def test_measurement_detail_is_jsonb():
    assert isinstance(models.Measurement.__table__.c.detail_json.type, JSONB)


def test_analysis_job_has_a_persisted_status_and_retry_count():
    cols = {c.name for c in models.AnalysisJob.__table__.columns}
    assert {"status", "attempts", "error_text"} <= cols


def test_reference_entities_are_keyed_by_a_stable_business_key():
    for model in (models.Persona, models.Scenario, models.MetricType):
        assert model.__table__.c.key.unique


def test_authored_reference_rows_carry_an_external_id_and_ownership():
    cols = {c.name: c for c in models.Scenario.__table__.columns}
    assert cols["extern_id"].unique
    assert cols["key"].nullable
    assert cols["created_by"].nullable
    checks = {c.name for c in models.Scenario.__table__.constraints
              if c.__class__.__name__ == "CheckConstraint"}
    assert "ck_scenario_visibility_valid" in checks


def test_a_persona_is_addressed_by_extern_id_and_carries_no_authorship():
    cols = {c.name for c in models.Persona.__table__.columns}
    assert models.Persona.__table__.c.extern_id.unique
    assert not cols & {"created_by", "tenant_id", "visibility"}


def test_measurement_value_is_numeric():
    assert isinstance(models.Measurement.__table__.c.value.type, Numeric)


# Behaviour, not declaration, so a later migration cannot drop these unnoticed.


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
