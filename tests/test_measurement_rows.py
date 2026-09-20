"""One measured figure becoming one stored row (`backend/feedback/rows.py`).

Covers:
  ADR 0029  the figure and its `detail_json`
  ADR 0051  a Measurement belongs to a Session, and since ADR 0081 to one
            stretch of it -- which is the `segment` these rows carry
  ADR 0057  the metric keys are English, and a row can only be written against
            a seeded `metric_type`

Four writers built these rows by hand -- the live path, the wrap-up's segment
pass and two backfill scripts -- each with its own metric-id lookup, its own
rounding and its own silent drop of an unseeded key. This pins the shared one.

No database: the rows are constructed, not flushed. What is being tested is the
shape they are given, which is exactly what four copies could disagree about.
"""
import logging

from backend.db import models as db_models
from backend.feedback import rows
from backend.feedback.metrics import Measurement

# pylint: disable=missing-function-docstring

IDS = {"pace": 1, "pauses": 2}


def test_a_figure_becomes_a_row_at_the_stored_scale():
    [row] = rows.measurements(IDS, [Measurement("pace", 123.456789, {"words": 40})])

    assert row.metric_type_id == 1
    assert str(row.value) == "123.4568"
    assert row.detail_json == {"words": 40}
    assert row.segment == db_models.SEGMENT_CALL


def test_a_key_the_seed_does_not_know_is_dropped_and_said_so(caplog):
    """It cannot be stored -- the row it would point at does not exist -- but a
    figure vanishing from every Session with a passing suite is the failure this
    application is least able to see. It was dropped in silence in four places."""
    with caplog.at_level(logging.WARNING):
        written = rows.measurements(IDS, [
            Measurement("pace", 2.0),
            Measurement("no_such_metric", 1.0),
        ])

    assert [row.metric_type_id for row in written] == [1]
    assert "no_such_metric" in caplog.text


def test_a_backfilled_row_says_where_it_came_from_without_touching_the_figure():
    original = {"runs": 27}
    [row] = rows.measurements(IDS, [Measurement("pace", 1.25, original)], backfilled=True)

    assert row.detail_json == {"runs": 27, "backfilled": True}
    assert original == {"runs": 27}, "the caller's detail was mutated"
    assert str(row.value) == "1.2500"


def test_an_ordinary_row_carries_no_backfilled_key():
    [row] = rows.measurements(IDS, [Measurement("pace", 1.0, {"runs": 3})])

    assert "backfilled" not in row.detail_json


def test_a_segment_row_names_its_stretch_and_its_session():
    """The wrap-up's segment pass adds rows by `session_id` rather than through
    the relationship, because it has just deleted the ones it replaces."""
    [row] = rows.measurements(
        IDS, [Measurement("pauses", 4.0)],
        segment=db_models.SEGMENT_PRESSURE, session_id=77,
    )

    assert (row.segment, row.session_id) == (db_models.SEGMENT_PRESSURE, 77)


def test_rows_keep_the_order_they_were_measured_in():
    written = rows.measurements(IDS, [Measurement("pauses", 1.0), Measurement("pace", 2.0)])

    assert [row.metric_type_id for row in written] == [2, 1]
