"""Speech-to-text: one blocking call per Turn against the DiReKT gateway.

Whisper needs the whole utterance before it returns anything, so unlike the
dialogue and TTS legs this one cannot stream (ADR 0033). There is no fallback
model — a dead STT model fails the Turn (ADR 0011, ADR 0016).
"""

import logging
import time

from backend.clients.config import STT_CLIENT, STT_MODEL

logger = logging.getLogger(__name__)


async def transcribe(audio_bytes: bytes, filename: str, content_type: str | None, language_id: str) -> str:
    """Transcribe one recorded Turn of user speech.

    `language_id` is passed through though the model auto-detects and was
    measured to ignore it (docs/model-parameters.md). It hallucinates a short
    phrase ("Vielen Dank.") on near-silence, which a VAD misfire can let through.
    """
    started = time.monotonic()
    transcription = await STT_CLIENT.audio.transcriptions.create(
        model=STT_MODEL,
        file=(filename, audio_bytes, content_type),
        language=language_id,
    )
    # What the user said is personal data, and the log file is outside every
    # deletion path this application has (ADR 0066) — so the text never goes
    # into it, and there is no switch that puts it back. The length is the part
    # that is actually useful for spotting a misfire — an empty transcript, or
    # the short hallucination the docstring above warns about — and it says
    # nothing about the person. The duration beside it: STT is one blocking
    # call per Turn (Whisper needs the whole utterance), so it is a fixed floor
    # under every reply and worth seeing next to the LLM's own timing. One line
    # after the call, where there used to be one before it as well saying only
    # that the call was about to be made.
    logger.info(
        "Transcript received (%d characters) in %.2f s",
        len(transcription.text), time.monotonic() - started,
    )
    return transcription.text
