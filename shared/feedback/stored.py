"""Reading a stored Session back as the call it was (ADR 0102). Not in
`calls.py`, which imports no ORM on purpose."""

from __future__ import annotations

from collections.abc import Sequence

from shared.db import models as db_models
from shared.feedback.acoustics import TurnFacts
from shared.feedback.calls import Conversation, conversation
from shared.turn import Turn


def ordered_turns(session: db_models.Session) -> list[db_models.Turn]:
    # By `seq_index`: load order depends on the server.
    return sorted(session.turns, key=lambda turn: turn.seq_index)


def whole_call(session: db_models.Session) -> list[db_models.Measurement]:
    """One row per metric; the segment rows are left out."""
    return [m for m in session.measurements if m.segment == db_models.SEGMENT_CALL]


def user_texts(session: db_models.Session) -> list[str]:
    return [
        row.transcript for row in ordered_turns(session)
        if row.speaker == db_models.SPEAKER_USER
    ]


def exchanges(session: db_models.Session) -> list[tuple[Turn, db_models.Turn]]:
    """Stored utterances rebuilt into Turns, each with its row. A user row
    without stored facts reads as unmeasured."""
    rebuilt: list[tuple[Turn, db_models.Turn]] = []
    for index, row in enumerate(ordered_turns(session)):
        if row.speaker == db_models.SPEAKER_PERSONA:
            rebuilt.append((Turn(
                seq=index,
                persona_text=row.transcript,
                persona_offset_ms=row.start_offset_ms,
                persona_end_ms=_end(row),
            ), row))
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
        ), row))
    return rebuilt


def conversation_of(session: db_models.Session, turns: Sequence[Turn]) -> Conversation:
    """Fold with the Session's own language and casting; a slice folded without
    `reverse` would measure the opening the wrong way round."""
    return conversation(turns, session.language_code, session.scenario.reverse)


def _end(row: db_models.Turn) -> int | None:
    return None if row.duration_ms is None else row.start_offset_ms + row.duration_ms
