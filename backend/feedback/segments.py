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

What is deliberately absent: any figure comparing the two. No difference, no
ratio, no "held up well". The two numbers are put side by side and the reader
draws the comparison, because the size of a difference that means something is
exactly the norm ADR 0051 refuses to invent.
"""

from __future__ import annotations

import logging

from backend.db import models as db_models
from backend.feedback import metrics
from backend.feedback.acoustics import TurnFacts
from backend.session.models import Turn, conversation

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

    turns = _turns_from_rows(session, pressed_turn_ids)
    measured: dict[str, list[metrics.Measurement]] = {}
    for segment, wanted in (
        (db_models.SEGMENT_PRESSURE, True),
        (db_models.SEGMENT_REST, False),
    ):
        part = [turn for turn, pressed in turns if pressed is wanted]
        spoken_in = sum(1 for turn in part if turn.user_text)
        if spoken_in < MIN_UTTERANCES:
            continue
        call = conversation(part, session.language_code)
        values = [m for m in metrics.measure(call) if m.key in SEGMENT_METRIC_KEYS]
        if values:
            measured[segment] = values
    return measured


def _turns_from_rows(
    session: db_models.Session, pressed_turn_ids: set[int]
) -> list[tuple[Turn, bool]]:
    """Rebuild the in-memory exchanges from the stored utterances, each paired
    with whether it belongs to a pressing stretch.

    The inverse of `session/models.py::utterances`, and only as much of one as
    the metrics above need: the Persona's line gives its window, the user's
    gives its window and its stored facts. A Persona line opens an exchange and
    the user's answer closes it, which is how the call was spoken and how the
    pressure carries over -- a user utterance is under pressure because the
    line it answers was.

    A Turn whose user side has no stored facts keeps its text and loses its
    milliseconds, which is exactly the state `user_acoustics_complete=False`
    describes and which the derivations already know how to withhold on.
    """
    rebuilt: list[tuple[Turn, bool]] = []
    pressed = False
    for index, row in enumerate(sorted(session.turns, key=lambda t: t.seq_index)):
        if row.speaker == db_models.SPEAKER_PERSONA:
            # A new exchange starts here, and this line decides its pressure.
            pressed = row.turn_id in pressed_turn_ids
            rebuilt.append((Turn(
                seq=index,
                persona_text=row.transcript,
                persona_offset_ms=row.start_offset_ms,
                persona_end_ms=_end(row),
            ), pressed))
            continue

        facts = TurnFacts.from_json(row.acoustics_json) if row.acoustics_json else None
        rebuilt.append((Turn(
            seq=index,
            user_text=row.transcript,
            user_offset_ms=row.start_offset_ms,
            user_end_ms=_end(row),
            user_speech_ms=facts.speech_ms if facts else 0,
            user_phonation_ms=facts.phonation_ms if facts else 0,
            user_acoustics_complete=facts.complete if facts else False,
            pauses=list(facts.pauses) if facts else [],
            loudness_db=list(facts.loudness_db) if facts else [],
        ), pressed))
    return rebuilt


def _end(row: db_models.Turn) -> int | None:
    """The utterance's end on the Session's timeline, or None where it has no
    measured duration -- the same thing the column means."""
    return None if row.duration_ms is None else row.start_offset_ms + row.duration_ms
