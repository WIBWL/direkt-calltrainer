"""Speech-to-text client call."""

import logging

from backend.clients.config import CLIENT, STT_MODEL

logger = logging.getLogger("calltrainer")


async def transcribe(audio_bytes: bytes, filename: str, content_type: str | None, language_id: str) -> str:
    """Transcribe one full utterance. The STT endpoint has no partial/streaming
    output mode, so this is always a single blocking call. `language_id`
    (ISO-639-1, e.g. "de") pins the expected source language, so Whisper
    doesn't have to guess it from the audio alone."""
    logger.info("Transcribing via STT (%s, language=%s)...", STT_MODEL, language_id)
    transcription = await CLIENT.audio.transcriptions.create(
        model=STT_MODEL,
        file=(filename, audio_bytes, content_type),
        language=language_id,
    )
    logger.info("Transcript: %s", transcription.text)
    return transcription.text
