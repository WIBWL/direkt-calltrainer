"""The same metrics over the demanding stretches of a call and over the rest
(F-62 "composure under pressure", ADR 0081).

The goal asks a comparative question: does the way somebody speaks hold up when
the other side pushes back. Nothing in the application could answer it, because
every figure described the whole call and the whole call has both stretches in
it, averaged into each other.

Three things had to meet for this to be measurable, and they meet in this
module:

* **The stretches.** Which exchanges were demanding is a judgement about what
  was said, so the wrap-up makes it, in the model call it already makes
  (`generator`). It marks Persona utterances; a user utterance belongs to the
  stretch of the Persona line it answers.
* **The facts.** The audio is gone by then (ADR 0048), so the raw paraverbal
  facts of each user utterance are stored when the call ends
  (`turn.acoustics_json`). This module folds them straight back into the
  in-memory `Turn` the existing derivations take.
* **The derivations.** None are written here. A segment is a *slice of the same
  call*, so `conversation()` folds it exactly as it folds the whole, and the
  metric functions in `metrics.py` run unchanged. Anything else would be a
  second definition of speaking pace, differing from the first by accident.

**The store** is here too (`store`): the wrap-up names the pressing lines, and
this marks them, measures both stretches and writes the rows, behind a
savepoint of its own so a failure costs the segment figures and not the
wrap-up. It lived in `generator.py` until that module passed its line ceiling
on the strength of a feature that was not its own.

What is deliberately absent: any figure comparing the two. No difference, no
ratio, no "held up well". The two numbers are put side by side and the reader
draws the comparison, because the size of a difference that means something is
exactly the norm ADR 0051 refuses to invent.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session as DbSession

from backend.db import models as db_models
from backend.feedback import metrics, rows, stored
from backend.session.models import Turn

logger = logging.getLogger(__name__)

# The metrics computed per segment, and the reason each is here.
#
# Only figures that stay defined on a part of a call. `reaction_time` would be,
# but it is measured from the end of the *previous* Persona line, which for the
# first exchange of a segment lies in the other segment -- the figure would
# quietly describe the boundary. `questions` and `word_count` are counts: a
# count over a shorter stretch is a smaller number by construction and says
# nothing about how somebody spoke. `intonation` is a reading over a whole call
# with a voiced-speech floor under it (F-35), and a segment routinely falls
# under that floor.
SEGMENT_METRIC_KEYS = (
    "talk_share",
    "pace",
    "pauses",
    metrics.RUN_LENGTH_KEY,
    metrics.LOUDNESS_KEY,
)

# Under this many user utterances a segment is not measured at all. Two is not
# a stretch of a conversation, it is two sentences, and the figures would be
# read as though they were comparable with the whole call's.
MIN_UTTERANCES = 3


def measure_segments(
    session: db_models.Session, pressed_turn_ids: set[int]
) -> dict[str, list[metrics.Measurement]]:
    """The chosen metrics over the pressing stretches and over the remainder.

    Returns a dict keyed by `db_models.SEGMENT_PRESSURE` / `SEGMENT_REST`,
    with the segments that could not be measured simply absent -- the same rule
    `metrics.measure` follows for a metric it cannot compute. An empty result
    is the normal answer for a call where nobody pushed back, and it is not a
    failure.
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
    """The call's exchanges, each paired with whether it belongs to a pressing
    stretch.

    A Persona line opens an exchange and the user's answer closes it, which is
    how the call was spoken and how the pressure carries over -- a user
    utterance is under pressure because the line it answers was.
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
    """Mark the pressing utterances, measure the two stretches and store them
    (ADR 0081), from the ids the wrap-up named.

    Called by the wrap-up job (`generator`), which is what decides the split,
    in the same transaction as the wrap-up but behind its own failure
    boundary: these figures are an addition to a wrap-up, and a Session losing
    them is a smaller loss than a Session losing the wrap-up they hang off.
    A raise here would also retry the whole model call, which would be paying
    for a second opinion to fix an arithmetic problem.

    The boundary is a **savepoint**, not just an `except`. Catching a Python
    error is enough for a Python error, and the delete, the flush and the
    metric-type read here are SQL: after one of those fails, Postgres has
    aborted the transaction and every later statement raises
    `InFailedSqlTransaction` -- so the swallowed error would take the wrap-up,
    the job status and the commit with it, which is exactly backwards. Rolling
    back to the savepoint leaves the transaction usable and the wrap-up intact.

    Idempotent, because `scripts/requeue_feedback.py` re-runs this job over
    Sessions that already have rows: the previous segment rows go first. The
    whole-call rows are never touched -- they were written when the call ended
    and no model opinion has any business overwriting a measurement.
    """
    if pressure_turns is None:
        # Nobody judged this call: the key was missing, or the reply never
        # validated. Leaving `turn.pressed` NULL is what says so -- writing
        # False everywhere would record the opposite finding, "judged, nobody
        # pushed", which is a claim the model never made.
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
    # Persona rows only, and only ids from this Session: the same rule the
    # points' `turn_id` follows, and for the same reason -- a reference
    # that leads somewhere else is worse than none.
    wanted = set(pressure_turns)
    pressed_ids = {
        row.turn_id for row in session.turns
        if row.turn_id in wanted and row.speaker == db_models.SPEAKER_PERSONA
    }
    # Measure before anything is written. The other way round -- flags set,
    # rows deleted, then measured -- is not the rewrite ADR 0081 promises: a
    # measurement that throws is caught below and the wrap-up is kept, but
    # the delete and the flags have already committed with it. A re-queue of
    # a Session that had good segment rows then leaves it with none, and
    # with Persona rows marked `pressed` that nothing measures. Nothing here
    # touches `row.pressed`; it reads the id set it is handed.
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
