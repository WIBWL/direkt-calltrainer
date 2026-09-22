"""A stored Session on the wire (`backend/api/served.py`).

Covers:
  ADR 0051  the measurement list carries the whole call only, one entry per
            metric; the segment rows (ADR 0081) travel under their own key
  ADR 0064  the listing drops `detail_json` and the wrap-up text
  ADR 0066  the export carries every row the subject owns, as stored
  ADR 0091  the detail route serves the Reading beside the stored facts

Three shapes built from one Session, which used to be written out in two route
modules -- so a field added to a Measurement needed three edits and nothing
failed where one was forgotten. The shared parts are one place now; these pin
what each shape keeps and what it leaves out.

No database: the ORM rows are built in memory and never flushed. The HTTP
tests (`test_api.py`, `test_data_rights.py`) still run the same shapes
end to end.
"""
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from backend.api import served
from backend.db import models as db_models

# pylint: disable=missing-function-docstring

PACE = db_models.MetricType(key="pace", name="Sprechtempo", unit="WPM", aspect="how", active=True)


def _session() -> db_models.Session:
    """One finished call with a whole-call figure, a pressure figure, two
    Turns stored out of order and a finished wrap-up."""
    session = db_models.Session(
        extern_id=uuid.UUID(int=1),
        persona=db_models.Persona(name="Thomas", extern_id=uuid.UUID(int=2)),
        scenario=db_models.Scenario(title="Störung", reverse=False, category="operations"),
        language_code="de",
        status=db_models.STATUS_COMPLETED,
        started_at=datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
        ended_at=datetime(2026, 9, 1, 10, 5, tzinfo=UTC),
    )
    session.measurements = [
        db_models.Measurement(metric_type=PACE, value=Decimal("131.5"),
                              detail_json={"words": 263}, segment=db_models.SEGMENT_CALL),
        db_models.Measurement(metric_type=PACE, value=Decimal("150"),
                              detail_json={"words": 60}, segment=db_models.SEGMENT_PRESSURE),
    ]
    session.turns = [
        db_models.Turn(seq_index=1, speaker="user", start_offset_ms=3000,
                       duration_ms=1000, transcript="Guten Tag."),
        db_models.Turn(seq_index=0, speaker="persona", start_offset_ms=0,
                       duration_ms=2000, transcript="Hallo?"),
    ]
    session.findings = []
    session.jobs = [db_models.AnalysisJob(job_id=1, kind=db_models.JOB_KIND_FEEDBACK,
                                          status=db_models.JOB_DONE)]
    session.feedback = db_models.Feedback(
        summary="Ruhig geführt.", phase_language=None, tone_fit=None,
        created_at=datetime(2026, 9, 1, 10, 6, tzinfo=UTC), points=[],
    )
    return session


def test_every_shape_names_a_figure_the_same_way():
    session = _session()
    rows = [
        served.summary(session)["measurements"][0],
        served.detail(session, follow_up=None)["measurements"][0],
        served.export(session)["measurements"][0],
    ]

    for row in rows:
        assert (row["key"], row["name"], row["unit"]) == ("pace", "Sprechtempo", "WPM")


def test_the_measurement_list_is_the_whole_call_only():
    """A pressure row in the list would draw the metric twice (ADR 0051)."""
    session = _session()

    for shape in (served.summary(session), served.detail(session, follow_up=None)):
        assert [m["value"] for m in shape["measurements"]] == [131.5]
        assert [(s["segment"], s["value"]) for s in shape["segments"]] == [
            (db_models.SEGMENT_PRESSURE, 150.0)
        ]


def test_the_export_carries_every_row_as_stored():
    """The subject's own copy (ADR 0066): both rows, each saying which stretch
    it describes, with the detail exactly as it was written."""
    measurements = served.export(_session())["measurements"]

    assert [(m["segment"], m["detail"]) for m in measurements] == [
        (db_models.SEGMENT_CALL, {"words": 263}),
        (db_models.SEGMENT_PRESSURE, {"words": 60}),
    ]


def test_the_listing_leaves_out_the_detail_and_the_wrap_up_text():
    row = served.summary(_session())

    assert "detail" not in row["measurements"][0]
    assert "feedback" not in row
    assert row["has_feedback"] is True


def test_turns_are_served_in_call_order_whatever_order_they_were_loaded_in():
    session = _session()

    assert [t["transcript"] for t in served.detail(session, follow_up=None)["turns"]] == [
        "Hallo?", "Guten Tag."
    ]
    assert [t["text"] for t in served.export(session)["transcript"]] == [
        "Hallo?", "Guten Tag."
    ]


def test_status_means_the_session_on_the_listing_and_the_wrap_up_on_the_detail():
    """The collision CLAUDE.md warns about, pinned so it cannot quietly change."""
    session = _session()

    assert served.summary(session)["status"] == db_models.STATUS_COMPLETED
    assert served.summary(session)["feedback_status"] == db_models.JOB_DONE
    assert served.detail(session, follow_up=None)["status"] == db_models.JOB_DONE


def test_a_session_whose_job_row_is_missing_reads_as_failed():
    """Nothing will ever write that wrap-up; a fifth status would only be
    another way of saying so."""
    session = _session()
    session.jobs = []

    assert served.summary(session)["feedback_status"] == db_models.JOB_FAILED


def test_the_follow_up_the_route_found_is_passed_through():
    card = {"id": "x", "name": "Weiter", "short_description": "…"}

    assert served.detail(_session(), follow_up=card)["follow_up"] == card
