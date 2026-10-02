"""The same metrics over the demanding stretches of a call and over the rest
(F-62 "composure under pressure", ADR 0081). A segment is a slice of the same
call, folded and measured by the unchanged `metrics.py`. Nothing here compares
the two figures -- a meaningful difference is the norm ADR 0051 refuses.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session as DbSession

from backend.db import models as db_models
from backend.feedback import metrics, rows, stored
from backend.session.models import Turn

logger = logging.getLogger(__name__)

# Only figures that stay defined on a part of a call: not `reaction_time` (its
# first gap lies in the other segment), not counts (smaller by construction),
# not `intonation` (a segment falls under its voiced-speech floor, F-35).
SEGMENT_METRIC_KEYS = (
    "talk_share",
    "pace",
    "pauses",
    metrics.RUN_LENGTH_KEY,
    metrics.LOUDNESS_KEY,
)

# Under this many user utterances a segment is not measured at all.
MIN_UTTERANCES = 3


def measure_segments(
    session: db_models.Session, pressed_turn_ids: set[int]
) -> dict[str, list[metrics.Measurement]]:
    """The chosen metrics over the pressing stretches and over the remainder,
    keyed by `SEGMENT_PRESSURE` / `SEGMENT_REST`; an unmeasurable segment is
    absent. Empty is the normal answer when nobody pushed back.
    """
    if not pressed_turn_ids:
        return {}

    turns = _pressure_marked(session, pressed_turn_ids)
    measured: dict[str, list[metrics.Measurement]] = {}
    for segment, wanted in (
        (db_models.SEGMENT_PRESSURE, True),
        (db_models.SEGMENT_REST, False),
    ):
        part = [turn for turn, pressed in turns if pressed is wanted]
        spoken_in = sum(1 for turn in part if turn.user_text)
        if spoken_in < MIN_UTTERANCES:
            continue
        call = stored.conversation_of(session, part)
        values = [m for m in metrics.measure(call) if m.key in SEGMENT_METRIC_KEYS]
        if values:
            measured[segment] = values
    return measured


def _pressure_marked(
    session: db_models.Session, pressed_turn_ids: set[int]
) -> list[tuple[Turn, bool]]:
    """The call's exchanges, each paired with whether it is pressing. A user
    utterance takes the pressure of the Persona line it *answers* (off by one
    here would measure the wrong sentences while looking healthy).
    """
    marked: list[tuple[Turn, bool]] = []
    pressed = False
    for turn, row in stored.exchanges(session):
        if row.speaker == db_models.SPEAKER_PERSONA:
            # A new exchange starts here, and this line decides its pressure.
            pressed = row.turn_id in pressed_turn_ids
        marked.append((turn, pressed))
    return marked


def store(db: DbSession, session_id: int, pressure_turns: list[int] | None) -> None:
    """Mark the pressing utterances, measure both stretches and store them
    (ADR 0081), in the wrap-up's transaction but behind its own failure boundary.

    The boundary must be a **savepoint**, not just an `except`: after a failed
    SQL statement Postgres aborts the transaction, and the swallowed error would
    take the wrap-up and its commit with it. Idempotent for
    `scripts/requeue_feedback.py`; whole-call rows are never touched.
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
