"""Measured figures into rows (ADR 0029, 0051, 0081)."""
import logging

from shared.db import models as db_models
from shared.feedback import rows
from shared.feedback.metrics import Measurement

# pylint: disable=missing-function-docstring

IDS = {"pace": 1, "pauses": 2}


def _only(written: list) -> db_models.Measurement:
    """The one row a single figure became."""
    assert len(written) == 1, written
    return written[0]


def test_a_figure_becomes_a_row_at_the_stored_scale():
    row = _only(rows.measurements(IDS, [Measurement("pace", 123.456789, {"words": 40})]))

    assert row.metric_type_id == 1
    assert str(row.value) == "123.4568"
    assert row.detail_json == {"words": 40}
    assert row.segment == db_models.SEGMENT_CALL


def test_a_key_the_seed_does_not_know_is_dropped_and_said_so(caplog):
    with caplog.at_level(logging.WARNING):
        written = rows.measurements(IDS, [
            Measurement("pace", 2.0),
            Measurement("no_such_metric", 1.0),
        ])

    assert [row.metric_type_id for row in written] == [1]
    assert "no_such_metric" in caplog.text


def test_a_segment_row_names_its_stretch_and_its_session():
    row = _only(rows.measurements(
        IDS, [Measurement("pauses", 4.0)],
        segment=db_models.SEGMENT_PRESSURE, session_id=77,
    ))

    assert (row.segment, row.session_id) == (db_models.SEGMENT_PRESSURE, 77)


def test_rows_keep_the_order_they_were_measured_in():
    written = rows.measurements(IDS, [Measurement("pauses", 1.0), Measurement("pace", 2.0)])

    assert [row.metric_type_id for row in written] == [2, 1]
