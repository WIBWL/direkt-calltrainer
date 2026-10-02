"""Text-to-speech on KugelAudio, the only speech output (ADR 0103): a failure ends the Turn.

``synthesize_stream`` (live path) yields WAV pieces as generated, one ``stream_async``
per chunk over a pooled WebSocket; ``synthesize`` returns one WAV (health check,
fallback closing line). See docs/model-parameters.md for the measurements.

**Never leave a stream short of its ``final`` frame on the pooled socket** (ADR 0044
amendment): frames carry no request id, so the leftover audio and ``final`` are read
by the *next* request -- a one-chunk offset for the life of the connection. Both
paths therefore drop and re-warm the connection on any unfinished exit.

**One request at a time** (``_pool_lock``): two Sessions on the singleton socket get
a ``websockets`` ``ConcurrencyError`` that no TTS handler catches. The wait is one
sentence's synthesis at most.
"""

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

# Held for the whole of one request on the pooled connection -- the send, every
# frame read back, and the drop-and-re-warm that follows an unfinished one. See
# the module docstring. Everything that touches `KUGELAUDIO_CLIENT.tts` takes
# it, and nothing takes it twice: `_drop_and_rewarm` is the lock-free
# half of the reset, called from inside a held lock.
_pool_lock = asyncio.Lock()


async def prewarm() -> None:
    """Open KugelAudio's pooled streaming connection ahead of the first Turn.

    Called once from the app's lifespan. `stream_async` (which
    `synthesize_stream` uses) reuses this connection, so the first synthesis
    of the process skips the ~300-600 ms TCP+TLS+WebSocket handshake."""
    async with _pool_lock:  # it is the pooled connection this opens
        try:
            await KUGELAUDIO_CLIENT.tts.connect_async(KUGELAUDIO_MODEL)
            logger.info("KugelAudio streaming connection pre-warmed (%s)", KUGELAUDIO_MODEL)
        except Exception as e:  # pylint: disable=broad-except
            # Broad on purpose: the re-warm runs as a fire-and-forget task that
            # nobody awaits, so anything not caught here surfaces only when the
            # garbage collector reports an unretrieved task exception, long
            # after the call it belonged to (ADR 0055). A cold handshake on the
            # next chunk is the whole cost of failing here.
            logger.warning("KugelAudio pre-warm failed (harmless, first Turn pays cold start): %s", e)


async def synthesize_stream(text: str, voice: PersonaVoice, language_id: str) -> AsyncIterator[bytes]:
    """Synthesize one text chunk, yielding WAV audio pieces as they arrive.

    Raises `KugelAudioError` on any failure, even after the first piece: there is
    no fallback (ADR 0103) and re-synthesising would diverge from heard audio (ADR 0033).
    """
    # Spoken form, not written: German writes "1.400" and "6. Juli" with a
    # full stop that both the chunker and the TTS read as a sentence end.
    # Done here so the Transcript keeps the digits.
    text = for_speech(text, language_id)
    # Never the text: the Persona's line carries the user's name and facts into a
    # file no deletion path reaches (ADR 0066). Debug, since this fires per chunk.
    logger.debug(
        "Synthesizing (streaming) via KugelAudio (voice=%s, language=%s, %d characters)",
        voice.kugelaudio_voice_id, language_id, len(text),
    )
    try:
        async with contextlib.aclosing(_pooled_request(text, voice, language_id)) as chunks:
            async for chunk in chunks:
                yield _pcm16_to_wav(chunk.audio, chunk.sample_rate)
    except (TimeoutError, OSError) as e:
        # Re-raised as a KugelAudioError so every caller has one exception to
        # catch for "the voice failed" rather than one per transport mishap.
        raise KugelAudioError(f"KugelAudio stream failed: {e}") from e


async def _pooled_request(text: str, voice: PersonaVoice, language_id: str) -> AsyncIterator[AudioChunk]:
    """One request on the pooled KugelAudio connection, and the only way onto it.

    Holds the lock for the whole request, across the yields (the connection is
    in use until `final`), and drops and re-warms the socket on any exit short
    of `final` (module docstring). Consume it under `contextlib.aclosing`: a
    caller that stops early must reach the `finally` now, not at GC time, or the
    next request reads this one's frames.
    """
    finished = False  # the request's `final` frame was read: the socket is clean
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
            # Reached on every exit: exhausted, failed, cancelled, or closed by
            # the caller after a barge-in.
            if not finished:
                await _drop_and_rewarm()


# Fire-and-forget re-warms, referenced so the loop cannot collect them mid-flight.
_background: set[asyncio.Task[None]] = set()


async def _drop_and_rewarm() -> None:
    """Drop the pooled streaming socket and warm a fresh one in the background.

    Call with `_pool_lock` held; the re-warm it schedules takes the lock itself.
    """
    try:
        # kugelaudio 1.9.0 has no public call for this; this is the one it uses internally.
        await KUGELAUDIO_CLIENT.tts._close_ws_connection()  # pylint: disable=protected-access
    except Exception as e:  # pylint: disable=broad-exception-caught  # a dead socket must not fail the Turn
        logger.warning("KugelAudio pooled connection could not be closed: %s", e)
    logger.info("KugelAudio pooled connection dropped after an unfinished stream; re-warming")
    task = asyncio.create_task(prewarm())
    _background.add(task)
    task.add_done_callback(_background.discard)


async def synthesize(text: str, voice: PersonaVoice, language_id: str) -> bytes:
    """One-shot: the whole chunk as a single WAV, through the same guarded `_pooled_request`.

    KugelAudio wants the bare language code ("de", "en"); it rejects "de-DE"
    with "Invalid request".
    """
    # Spoken form, not written: German writes "1.400" and "6. Juli" with a
    # full stop that both the chunker and the TTS read as a sentence end.
    # Done here so the Transcript keeps the digits.
    text = for_speech(text, language_id)
    # Same rule as the streaming path above, for the same reasons.
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
    """Playback length of one synthesized chunk.

    0 for anything unreadable: it places the Persona on the Session's timeline
    (ADR 0051), which must not be able to fail a call.
    """
    try:
        with wave.open(io.BytesIO(wav_bytes)) as wav:
            return round(wav.getnframes() * 1000 / wav.getframerate())
    except (wave.Error, ZeroDivisionError, EOFError):
        logger.warning("Synthesized chunk has no readable WAV header; timing it as 0 ms")
        return 0
