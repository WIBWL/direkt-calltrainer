"""Reading a stored Session back as the call it was (ADR 0102); `rows.py` is the
way in. Computes nothing: rows in the order and subset readers need, and a fold
that takes language and casting from the Session so neither can be forgotten.
Not in `calls.py`, which imports no ORM on purpose.
"""

from __future__ import annotations

from collections.abc import Sequence

from backend.db import models as db_models
from backend.feedback.acoustics import TurnFacts
from backend.feedback.calls import Conversation, conversation
from backend.session.models import Turn


def ordered_turns(session: db_models.Session) -> list[db_models.Turn]:
    """The stored utterances in the order they were said. `seq_index`, not the
    load order, which depends on the server (migration `a7c39e5f21b8`)."""
    return sorted(session.turns, key=lambda turn: turn.seq_index)


def whole_call(session: db_models.Session) -> list[db_models.Measurement]:
    """The whole call's figures, one per metric (ADR 0051). The rows over the
    demanding stretches and the rest (ADR 0081) are left out: every reader of
    this list assumes one entry per metric."""
    return [m for m in session.measurements if m.segment == db_models.SEGMENT_CALL]


def user_texts(session: db_models.Session) -> list[str]:
    """What the user said, one entry per utterance, in order -- the same unit
    `Conversation.user_turns` counts in the live path."""
    return [
        row.transcript for row in ordered_turns(session)
        if row.speaker == db_models.SPEAKER_USER
    ]


def exchanges(session: db_models.Session) -> list[tuple[Turn, db_models.Turn]]:
    """The stored utterances rebuilt into in-memory Turns, each paired with its
    row -- the inverse of `calls.utterances`, as far as the metrics need one. A
    user row without stored facts reads as `user_acoustics_complete=False`.
    """
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
    """Fold `turns` -- all of this Session's, or a slice of them -- with the
    Session's own language and casting. The casting matters to any metric that
    reads who rang (`opening`, ADR 0086); a slice folded without it would be
    measured as an ordinary call."""
    return conversation(turns, session.language_code, session.scenario.reverse)


def _end(row: db_models.Turn) -> int | None:
    """The utterance's end on the Session's timeline, or None where it has no
    measured duration -- the same thing the column means."""
    return None if row.duration_ms is None else row.start_offset_ms + row.duration_ms
