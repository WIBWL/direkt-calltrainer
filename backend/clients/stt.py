"""Speech-to-text, one blocking call per Turn; no fallback (ADR 0033, 0103)."""

import logging
import time

from backend.clients.config import STT_CLIENT, STT_MODEL

logger = logging.getLogger(__name__)


async def transcribe(audio_bytes: bytes, filename: str, content_type: str | None, language_id: str) -> str:
    """Whisper hallucinates a short phrase on near-silence (ADR 0071)."""
    started = time.monotonic()
    transcription = await STT_CLIENT.audio.transcriptions.create(
        model=STT_MODEL,
        file=(filename, audio_bytes, content_type),
        language=language_id,
    )
    # Never the text: the log is outside every deletion path (ADR 0066).
    logger.info(
        "Transcript received (%d characters) in %.2f s",
        len(transcription.text), time.monotonic() - started,
    )
    return transcription.text
