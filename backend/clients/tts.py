"""KugelAudio, the only speech output (ADR 0103); a failure ends the Turn.

**Never leave a stream short of its `final` frame** (ADR 0044): frames carry no
request id, so leftovers would be read by the next request. Any unfinished exit
drops and re-warms the pooled connection. **One request at a time**
(`_pool_lock`): concurrent use raises a ConcurrencyError nobody handles."""

import asyncio
import contextlib
import io
import logging
import wave
from collections.abc import AsyncIterator

from kugelaudio.exceptions import KugelAudioError
from kugelaudio.models import AudioChunk

from backend.clients.config import KUGELAUDIO_CLIENT, KUGELAUDIO_MODEL
from backend.clients.speech_text import for_speech
from backend.personas import PersonaVoice

logger = logging.getLogger(__name__)

# Held across one whole request, its frames and any reset; never taken twice
# (`_drop_and_rewarm` runs inside it).
_pool_lock = asyncio.Lock()


async def prewarm() -> None:
    """Skips the cold handshake (~300-600 ms) on the first synthesis."""
    async with _pool_lock:
        try:
            await KUGELAUDIO_CLIENT.tts.connect_async(KUGELAUDIO_MODEL)
            logger.info("KugelAudio streaming connection pre-warmed (%s)", KUGELAUDIO_MODEL)
        except Exception as e:  # pylint: disable=broad-except
            # The re-warm is a fire-and-forget task; uncaught, this would vanish.
            logger.warning("KugelAudio pre-warm failed (harmless, first Turn pays cold start): %s", e)


async def synthesize_stream(text: str, voice: PersonaVoice, language_id: str) -> AsyncIterator[bytes]:
    """Raises KugelAudioError on any failure, even mid-stream: no fallback, and
    re-synthesising would diverge from what was heard."""
    # The spoken form; the transcript keeps the digits.
    text = for_speech(text, language_id)
    # Never the text (ADR 0066). Debug: this fires per chunk.
    logger.debug(
        "Synthesizing (streaming) via KugelAudio (voice=%s, language=%s, %d characters)",
        voice.kugelaudio_voice_id, language_id, len(text),
    )
    try:
        async with contextlib.aclosing(_pooled_request(text, voice, language_id)) as chunks:
            async for chunk in chunks:
                yield _pcm16_to_wav(chunk.audio, chunk.sample_rate)
    except (TimeoutError, OSError) as e:
        # One exception type for "the voice failed".
        raise KugelAudioError(f"KugelAudio stream failed: {e}") from e


async def _pooled_request(text: str, voice: PersonaVoice, language_id: str) -> AsyncIterator[AudioChunk]:
    """The only way onto the pooled connection. Consume it under `aclosing`, so
    an early stop reaches the reset now, not at GC time."""
    finished = False
    async with _pool_lock:
        try:
            async for event in KUGELAUDIO_CLIENT.tts.stream_async(
                text=text,
                model_id=KUGELAUDIO_MODEL,
                voice_id=voice.kugelaudio_voice_id,
                language=language_id,
            ):
                if isinstance(event, AudioChunk):
                    yield event
                elif isinstance(event, dict) and event.get("final"):
                    finished = True
        finally:
            if not finished:
                await _drop_and_rewarm()


_background: set[asyncio.Task[None]] = set()


async def _drop_and_rewarm() -> None:
    """Call with `_pool_lock` held; the re-warm takes the lock itself."""
    try:
        # kugelaudio 1.9.0 has no public call for this.
        await KUGELAUDIO_CLIENT.tts._close_ws_connection()  # pylint: disable=protected-access
    except Exception as e:  # pylint: disable=broad-exception-caught  # a dead socket must not fail the Turn
        logger.warning("KugelAudio pooled connection could not be closed: %s", e)
    logger.info("KugelAudio pooled connection dropped after an unfinished stream; re-warming")
    task = asyncio.create_task(prewarm())
    _background.add(task)
    task.add_done_callback(_background.discard)


async def synthesize(text: str, voice: PersonaVoice, language_id: str) -> bytes:
    """One WAV. KugelAudio rejects "de-DE"; it wants the bare code."""
    # The spoken form; the transcript keeps the digits.
    text = for_speech(text, language_id)
    logger.debug("Synthesizing via KugelAudio (voice=%s, language=%s, %d characters)",
                 voice.kugelaudio_voice_id, language_id, len(text))
    pcm = bytearray()
    sample_rate = 24000
    async with contextlib.aclosing(_pooled_request(text, voice, language_id)) as chunks:
        async for chunk in chunks:
            pcm += chunk.audio
            sample_rate = chunk.sample_rate

    if not pcm:
        raise KugelAudioError("KugelAudio returned no audio")

    return _pcm16_to_wav(bytes(pcm), sample_rate)


def _pcm16_to_wav(pcm_bytes: bytes, sample_rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.Wave_write(buf) as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm_bytes)
    return buf.getvalue()


def duration_ms(wav_bytes: bytes) -> int:
    """0 if unreadable: timing must never fail a call."""
    try:
        with wave.open(io.BytesIO(wav_bytes)) as wav:
            return round(wav.getnframes() * 1000 / wav.getframerate())
    except (wave.Error, ZeroDivisionError, EOFError):
        logger.warning("Synthesized chunk has no readable WAV header; timing it as 0 ms")
        return 0
