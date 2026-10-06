"""Stores the measurements over the demanding stretches (ADR 0081)."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session as DbSession

from shared.db import models as db_models
from shared.feedback import rows
from shared.feedback.segments import measure_segments

logger = logging.getLogger(__name__)


def store(db: DbSession, session_id: int, pressure_turns: list[int] | None) -> None:
    """In the wrap-up's transaction, behind a savepoint: after a failed statement
    Postgres aborts the whole transaction, so a bare `except` would lose the
    wrap-up too. Idempotent; whole-call rows are never touched."""
    if pressure_turns is None:
        # Unjudged stays NULL; False would claim "judged, nobody pushed".
        logger.info("Session %d: no pressure judgement in the wrap-up; leaving the rows unmarked", session_id)
        return
    try:
        with db.begin_nested():
            _write(db, session_id, pressure_turns)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Segment measurement failed for session %d", session_id)


def _write(db: DbSession, session_id: int, pressure_turns: list[int]) -> None:
    session = db.get(db_models.Session, session_id)
    if session is None:
        return
    # Persona rows of this Session only, like the points' `turn_id`.
    wanted = set(pressure_turns)
    pressed_ids = {
        row.turn_id for row in session.turns
        if row.turn_id in wanted and row.speaker == db_models.SPEAKER_PERSONA
    }
    # Measure before writing anything, or a failure leaves marks without rows.
    measured = measure_segments(session, pressed_ids)

    for row in session.turns:
        if row.speaker == db_models.SPEAKER_PERSONA:
            row.pressed = row.turn_id in pressed_ids

    db.query(db_models.Measurement).filter(
        db_models.Measurement.session_id == session_id,
        db_models.Measurement.segment != db_models.SEGMENT_CALL,
    ).delete(synchronize_session=False)
    db.flush()

    ids = rows.metric_ids(db)
    for segment, values in measured.items():
        db.add_all(rows.measurements(ids, values, segment=segment, session_id=session_id))
    logger.info(
        "Segment measurements for session %d: %d pressing utterance(s)",
        session_id, len(pressed_ids),
    )
