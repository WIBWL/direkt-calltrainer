"""Speech-to-text: one blocking call per Turn against the DiReKT gateway.

Whisper needs the whole utterance before it returns anything, so unlike the
dialogue and TTS legs this one cannot stream (ADR 0033). There is no fallback
model — a dead STT model fails the Turn (ADR 0011, ADR 0016).
"""

import logging

from backend.clients.config import LOG_TRANSCRIPTS, STT_CLIENT, STT_MODEL

logger = logging.getLogger(__name__)


async def transcribe(audio_bytes: bytes, filename: str, content_type: str | None, language_id: str) -> str:
    """Transcribe one recorded Turn of user speech.

    `language_id` is passed through though the model auto-detects and was
    measured to ignore it (docs/model-parameters.md). It hallucinates a short
    phrase ("Vielen Dank.") on near-silence, which a VAD misfire can let through.
    """
    logger.info("Transcribing via STT (%s, language=%s)...", STT_MODEL, language_id)
    transcription = await STT_CLIENT.audio.transcriptions.create(
        model=STT_MODEL,
        file=(filename, audio_bytes, content_type),
        language=language_id,
    )
    # What the user said is personal data, and the log file is outside every
    # deletion path this application has (ADR 0060). The length is the part
    # that is actually useful for spotting a misfire — an empty transcript, or
    # the short hallucination the docstring above warns about — and it says
    # nothing about the person. The text itself only under LOG_TRANSCRIPTS.
    if LOG_TRANSCRIPTS:
        logger.info("Transcript: %s", transcription.text)
    else:
        logger.info("Transcript received (%d characters)", len(transcription.text))
    return transcription.text
