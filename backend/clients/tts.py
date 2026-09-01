"""Text-to-speech client calls.

Two shapes:

* ``synthesize_stream`` — the live path. Streams one text chunk through
  KugelAudio and yields WAV pieces **as they are generated**, so the first
  audio reaches the client ~0.3 s after the chunk is ready instead of ~0.9 s
  (measured; see ``docs/model-parameters.md``). One ``stream_async`` call per
  chunk over a pooled WebSocket (``reuse_connection`` + ``prewarm``); the
  KugelAudio doc's persistent ``streaming_session`` was measured *slower* to
  first audio with this SDK because its per-``send`` poll defers synthesis to
  the final flush.
* ``synthesize`` — one-shot, returns the whole chunk as a single WAV. Used by
  the startup health check and the fixed fallback-closing line, where first-
  audio latency does not matter.

Both fall back to the DiReKT Voxtral model (ADR 0040) when KugelAudio fails
before producing audio, or always under ``DEBUG``.
"""

import io
import logging
import wave
from collections.abc import AsyncIterator

from kugelaudio.exceptions import KugelAudioError
from kugelaudio.models import AudioChunk
from openai import OpenAIError

from backend.clients.config import CLIENT, DEBUG, KUGELAUDIO_CLIENT, KUGELAUDIO_MODEL, TTS_MODEL
from backend.personas import PersonaVoice

logger = logging.getLogger(__name__)


async def prewarm() -> None:
    """Open KugelAudio's pooled streaming connection ahead of the first Turn.

    Called once from the app's lifespan. `stream_async` (which
    `synthesize_stream` uses) reuses this connection, so the first synthesis
    of the process skips the ~300-600 ms TCP+TLS+WebSocket handshake. No-op
    under DEBUG."""
    if DEBUG or KUGELAUDIO_CLIENT is None:
        return
    try:
        await KUGELAUDIO_CLIENT.tts.connect_async(KUGELAUDIO_MODEL)
        logger.info("KugelAudio streaming connection pre-warmed (%s)", KUGELAUDIO_MODEL)
    except (KugelAudioError, TimeoutError, OSError) as e:
        logger.warning("KugelAudio pre-warm failed (harmless, first Turn pays cold start): %s", e)


async def synthesize_stream(text: str, voice: PersonaVoice, language_id: str) -> AsyncIterator[bytes]:
    """Synthesize one text chunk, yielding WAV audio pieces as they arrive.

    Falls back to one DiReKT batch WAV if KugelAudio fails *before* producing any
    audio. Raises `KugelAudioError` if it fails *after* — a fresh synthesis
    would diverge from audio the user has already heard (ADR 0033), so the
    caller ends the Turn instead.
    """
    if DEBUG or KUGELAUDIO_CLIENT is None:
        yield await _synthesize(text, voice)
        return

    logger.info(
        "Synthesizing (streaming) via KugelAudio (%s, voice=%s, language=%s): %r",
        KUGELAUDIO_MODEL, voice.kugelaudio_voice_id, language_id, text,
    )
    produced = False
    try:
        async for event in KUGELAUDIO_CLIENT.tts.stream_async(
            text=text,
            model_id=KUGELAUDIO_MODEL,
            voice_id=voice.kugelaudio_voice_id,
            language=language_id,
        ):
            if isinstance(event, AudioChunk):
                produced = True
                yield _pcm16_to_wav(event.audio, event.sample_rate)
    except (KugelAudioError, TimeoutError, OSError) as e:
        if produced:
            raise KugelAudioError(f"KugelAudio stream failed after producing audio: {e}") from e
        logger.warning("KugelAudio streaming failed before any audio, falling back to DiReKT: %s", e)
        yield await _synthesize(text, voice)


async def synthesize(text: str, voice: PersonaVoice, language_id: str) -> bytes:
    """One-shot: the whole chunk as a single WAV. KugelAudio by default,
    DiReKT on failure or under DEBUG."""
    if not DEBUG:
        try:
            return await _synthesize_kugelaudio(text, voice, language_id)
        except (KugelAudioError, TimeoutError, OSError) as e:
            logger.warning("KugelAudio TTS failed, falling back to DiReKT: %s", e)
    return await _synthesize(text, voice)


async def _synthesize_kugelaudio(text: str, voice: PersonaVoice, language_id: str) -> bytes:
    pcm = bytearray()
    sample_rate = 24000
    async for event in KUGELAUDIO_CLIENT.tts.stream_async(
        text=text,
        model_id=KUGELAUDIO_MODEL,
        voice_id=voice.kugelaudio_voice_id,
        language=language_id,
    ):
        if isinstance(event, AudioChunk):
            pcm += event.audio
            sample_rate = event.sample_rate
    return _pcm16_to_wav(bytes(pcm), sample_rate)


async def _synthesize(text: str, voice: PersonaVoice) -> bytes:
    """DiReKT Voxtral batch call, one retry (ADR 0016)."""
    last_err: OpenAIError | None = None
    for attempt in range(2):
        try:
            logger.info("Synthesizing speech via DiReKT TTS (%s, voice=%s): %r", TTS_MODEL, voice.tts_voice, text)
            speech = await CLIENT.audio.speech.create(
                model=TTS_MODEL,
                voice=voice.tts_voice,
                input=text,
                response_format="wav",
            )
            return speech.content
        except OpenAIError as e:
            last_err = e
            logger.error("DiReKT TTS failed (attempt %d): %s", attempt + 1, e)
    raise last_err  # type: ignore[misc]


def _pcm16_to_wav(pcm_bytes: bytes, sample_rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.Wave_write(buf) as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm_bytes)
    return buf.getvalue()
