"""Attaching one utterance's paraverbal measurements to its Turn (ADR 0048).

`analyze` (backend/feedback/acoustics.py) measures the audio on a worker thread
during the STT round trip; this places the result on the Session's timeline.
"""

import asyncio
import logging

from backend.feedback.acoustics import AcousticsError, Pause, TurnAcoustics
from backend.session.models import Turn

logger = logging.getLogger(__name__)


async def attach_measurements(
    turn: Turn, acoustics: asyncio.Task[TurnAcoustics], ended_ms: int
) -> None:
    """Record the Turn's paraverbal measurements, on the Session's timeline.

    `ended_ms` is where this fragment ends; the measured duration walks back to
    its start, so each fragment of a reopened Turn is placed by its own arrival.
    Never fatal: the conversation does not depend on this leg."""
    try:
        measured = await acoustics
    except AcousticsError as e:
        logger.info("Turn %d not measured: %s", turn.seq, e)
        turn.user_acoustics_complete = False
        return
    except Exception:  # pylint: disable=broad-exception-caught
        # Deliberately catch-all: `analyze` runs Praat in a worker thread and
        # can surface anything from the C extension. Per the docstring this leg
        # is never load-bearing, so any failure here is logged and the Turn
        # just carries no measurements -- it must not break the call.
        logger.exception("Paraverbal analysis failed for turn %d", turn.seq)
        turn.user_acoustics_complete = False
        return
    started_ms = max(0, ended_ms - measured.duration_ms)
    if turn.user_offset_ms is None:
        turn.user_offset_ms = started_ms
    turn.user_speech_ms += measured.duration_ms
    turn.user_phonation_ms += measured.phonation_ms
    turn.pauses.extend(Pause(started_ms + p.offset_ms, p.duration_ms) for p in measured.pauses)
    turn.loudness_db.extend(measured.loudness_db)
    # Same grid, same concatenation: the pitch curve carries no offsets of its
    # own, so it needs no rebasing (F-35).
    turn.pitch_hz.extend(measured.pitch_hz)
