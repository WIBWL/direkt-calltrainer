"""The same metrics over the demanding stretches of a call and over the rest
(F-62 "composure under pressure", ADR 0081). A segment is a slice of the same
call, folded and measured by the unchanged `metrics.py`. Nothing here compares
the two figures -- a meaningful difference is the norm ADR 0051 refuses.

Measuring only; `worker/segments.py` stores the result.
"""

from __future__ import annotations

from shared.db import models as db_models
from shared.feedback import metrics, stored
from shared.turn import Turn

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
