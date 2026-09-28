"""Speech-to-text: one blocking call per Turn against the DiReKT gateway.

Whisper needs the whole utterance, so this leg cannot stream (ADR 0033). No
fallback: a dead STT model fails the Turn (ADR 0011, ADR 0016)."""

import logging
import time

from backend.clients.config import STT_CLIENT, STT_MODEL

logger = logging.getLogger(__name__)


async def transcribe(audio_bytes: bytes, filename: str, content_type: str | None, language_id: str) -> str:
    """Transcribe one recorded Turn of user speech.

    `language_id` is passed though the model auto-detects and ignores it. It
    hallucinates a short phrase ("Vielen Dank.") on near-silence."""
    started = time.monotonic()
    transcription = await STT_CLIENT.audio.transcriptions.create(
        model=STT_MODEL,
        file=(filename, audio_bytes, content_type),
        language=language_id,
    )
    # Never the text: it is personal data and the log file is outside every
    # deletion path (ADR 0066). The length still catches an empty transcript or a
    # hallucination; the duration is a fixed floor under every reply.
    logger.info(
        "Transcript received (%d characters) in %.2f s",
        len(transcription.text), time.monotonic() - started,
    )
    return transcription.text
