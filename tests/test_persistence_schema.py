"""The persistence schema (SQLAlchemy models).

Covers:
  ADR 0026  normalized schema for session persistence
  ADR 0025  SQLAlchemy ORM as the single source of truth
  ADR 0030  metric types carry a `feature_id` linking a measurement back to
            a feature in docs/features.md (F-24, F-35..F-38, F-51, ...)
  ADR 0029  measurement detail is JSONB
  F-09/F-14  Feedback row: qualitative summary (NOT NULL) + optional score
  F-12      Turn transcripts are stored

These are structural assertions on the mapper metadata; the schema is not
yet wired into the app (see test_documented_gaps.py).
"""

from sqlalchemy import Numeric, inspect
from sqlalchemy.dialects.postgresql import JSONB

from backend.db import models
from backend.db.base import Base

# pylint: disable=missing-function-docstring


def test_every_domain_table_is_present():
    expected = {
        "persona", "persona_einwand", "szenario", "sprache", "metrik_typ",
        "session", "turn", "messung", "befund", "feedback", "feedbackpunkt",
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
    assert "transkript" in cols
    assert "sprecher" in cols  # nutzer | persona


def test_feedback_summary_is_mandatory_and_score_is_optional():
    """F-09/F-14: a qualitative summary is required; the numeric score is not."""
    cols = {c.name: c for c in models.Feedback.__table__.columns}
    assert cols["zusammenfassung"].nullable is False
    assert cols["score"].nullable is True
    assert models.Feedback.__table__.c.session_id.unique  # one feedback per session


def test_metric_type_links_a_measurement_to_a_feature():
    """ADR 0030: `feature_id` on metrik_typ is how a stored measurement is
    traced back to a functional requirement in docs/features.md."""
    cols = {c.name for c in models.MetrikTyp.__table__.columns}
    assert "feature_id" in cols
    assert "schluessel" in cols  # e.g. 'intonation', 'tempo'


def test_measurement_detail_is_jsonb():
    """ADR 0029: per-turn metric course is stored as JSONB."""
    assert isinstance(models.Messung.__table__.c.detail_json.type, JSONB)


def test_analysis_job_has_a_persisted_status_and_retry_count():
    """ADR 0032: job outcome/status is persisted (queued|running|done|failed)."""
    cols = {c.name for c in models.AnalysisJob.__table__.columns}
    assert {"status", "versuche", "fehlertext"} <= cols


def test_reference_entities_are_keyed_by_a_stable_business_key():
    for model in (models.Persona, models.Szenario, models.MetrikTyp):
        assert model.__table__.c.schluessel.unique


def test_messung_value_is_numeric():
    assert isinstance(models.Messung.__table__.c.wert.type, Numeric)
