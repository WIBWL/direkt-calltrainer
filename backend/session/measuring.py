"""Places one utterance's acoustic measurements on the Session timeline (ADR 0048)."""

import asyncio
import logging

from shared.feedback.acoustics import AcousticsError, Pause, TurnAcoustics
from shared.turn import Turn

logger = logging.getLogger(__name__)


async def attach_measurements(
    turn: Turn, acoustics: asyncio.Task[TurnAcoustics], ended_ms: int
) -> None:
    """`ended_ms` is where this fragment ends; each fragment of a reopened Turn
    is placed by its own arrival. Never fatal."""
    try:
        measured = await acoustics
    except AcousticsError as e:
        logger.info("Turn %d not measured: %s", turn.seq, e)
        turn.user_acoustics_complete = False
        return
    except Exception:  # pylint: disable=broad-exception-caught
        # Praat can surface anything from the C extension; this leg is never load-bearing.
        logger.exception("Paraverbal analysis failed for turn %d", turn.seq)
        turn.user_acoustics_complete = False
        return
    started_ms = max(0, ended_ms - measured.duration_ms)
    # First sound to last, not the padded recording (ADR 0114). Pauses stay
    # relative to the recording start.
    if turn.user_offset_ms is None:
        turn.user_offset_ms = started_ms + measured.voice_start_ms
    turn.user_end_ms = started_ms + measured.voice_end_ms
    turn.user_speech_ms += measured.duration_ms
    turn.user_phonation_ms += measured.phonation_ms
    turn.pauses.extend(Pause(started_ms + p.offset_ms, p.duration_ms) for p in measured.pauses)
    turn.loudness_db.extend(measured.loudness_db)
    turn.pitch_hz.extend(measured.pitch_hz)
