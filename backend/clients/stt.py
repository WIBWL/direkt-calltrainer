"""Speech-to-text client call."""

import logging

from backend.clients.config import STT_CLIENT, STT_MODEL

logger = logging.getLogger("calltrainer")


async def transcribe(audio_bytes: bytes, filename: str, content_type: str | None, language_id: str) -> str:
    """Transcribe one full utterance."""
    logger.info("Transcribing via STT (%s, language=%s)...", STT_MODEL, language_id)
    transcription = await STT_CLIENT.audio.transcriptions.create(
        model=STT_MODEL,
        file=(filename, audio_bytes, content_type),
        language=language_id,
    )
    logger.info("Transcript: %s", transcription.text)
    return transcription.text
