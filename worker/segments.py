"""Stores the demanding stretches of a call and the rest, measured separately
(F-62, ADR 0081), in the wrap-up's transaction. The measuring is
`shared/feedback/segments.py`.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session as DbSession

from shared.db import models as db_models
from shared.feedback import rows
from shared.feedback.segments import measure_segments

logger = logging.getLogger(__name__)


def store(db: DbSession, session_id: int, pressure_turns: list[int] | None) -> None:
    """Mark the pressing utterances, measure both stretches and store them
    (ADR 0081), in the wrap-up's transaction but behind its own failure boundary.

    The boundary must be a **savepoint**, not just an `except`: after a failed
    SQL statement Postgres aborts the transaction, and the swallowed error would
    take the wrap-up and its commit with it. Idempotent for
    `backend/scripts/requeue_feedback.py`; whole-call rows are never touched.
    """
    if pressure_turns is None:
        # Nobody judged this call: leave `turn.pressed` NULL. False would claim
        # "judged, nobody pushed", which the model never said.
        logger.info("Session %d: no pressure judgement in the wrap-up; leaving the rows unmarked", session_id)
        return
    try:
        with db.begin_nested():
            _write(db, session_id, pressure_turns)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Segment measurement failed for session %d", session_id)


def _write(db: DbSession, session_id: int, pressure_turns: list[int]) -> None:
    """The body of `store`, inside its savepoint. See there."""
    session = db.get(db_models.Session, session_id)
    if session is None:
        return
    # Persona rows of this Session only, like the points' `turn_id`.
    wanted = set(pressure_turns)
    pressed_ids = {
        row.turn_id for row in session.turns
        if row.turn_id in wanted and row.speaker == db_models.SPEAKER_PERSONA
    }
    # Measure before anything is written: if measuring throws after the delete
    # and the flags, those still commit with the wrap-up, and a re-queue would
    # leave a Session with no segment rows and unmeasured `pressed` marks.
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
