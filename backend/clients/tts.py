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

**A stream left before its ``final`` frame poisons the pooled socket** (ADR
0044 amendment). ``stream_async`` sends the request on the shared connection
and reads frames until ``final`` -- with no request id to tell one request's
frames from the next. A barge-in closes the Turn generator mid-stream, so that
request's remaining audio *and* its ``final`` stay queued on the socket; the
next ``stream_async`` then yields that stale audio as its own, ends on the stale
``final``, and leaves its own frames for the call after it -- a one-chunk
offset that persists for the life of the connection. Live, that was the
persona's last sentence arriving at the start of the *next* Turn, every Turn,
once a call had been interrupted mid-sentence. So ``synthesize_stream`` drops
the pooled connection whenever it is left short of ``final`` and re-warms a
fresh one off the critical path (``kugelaudio==1.9.0`` has no public call for
this; ``_close_ws_connection`` is the one it uses internally).
"""

import asyncio
import io
import logging
import wave
from collections.abc import AsyncIterator

from kugelaudio.exceptions import KugelAudioError
from kugelaudio.models import AudioChunk
from openai import OpenAIError

from backend.clients.config import (
    CLIENT,
    DEBUG,
    KUGELAUDIO_CLIENT,
    KUGELAUDIO_MODEL,
    LOG_TRANSCRIPTS,
    TTS_MODEL,
)
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
    finished = False  # the request's `final` frame was read: the socket is clean
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
            elif isinstance(event, dict) and event.get("final"):
                finished = True
    except (KugelAudioError, TimeoutError, OSError) as e:
        if produced:
            raise KugelAudioError(f"KugelAudio stream failed after producing audio: {e}") from e
        logger.warning("KugelAudio streaming failed before any audio, falling back to DiReKT: %s", e)
        yield await _synthesize(text, voice)
    finally:
        # Reached on every exit: exhausted, failed, cancelled, or closed by the
        # caller after a barge-in. Anything short of `final` leaves this
        # request's frames on the shared socket (module docstring).
        if not finished:
            await _reset_pooled_connection()


# Fire-and-forget re-warms, referenced so the loop cannot collect them mid-flight.
_background: set[asyncio.Task[None]] = set()


async def _reset_pooled_connection() -> None:
    """Drop the pooled streaming socket and warm a fresh one in the background.

    The next chunk pays a cold handshake only if it arrives before the re-warm
    completes -- after a barge-in that is the next *Turn*, seconds away."""
    try:
        # No public equivalent in kugelaudio 1.9.0 (module docstring).
        await KUGELAUDIO_CLIENT.tts._close_ws_connection()  # pylint: disable=protected-access
    except Exception as e:  # pylint: disable=broad-exception-caught  # a dead socket must not fail the Turn
        logger.warning("KugelAudio pooled connection could not be closed: %s", e)
    logger.info("KugelAudio pooled connection dropped after an unfinished stream; re-warming")
    task = asyncio.create_task(prewarm())
    _background.add(task)
    task.add_done_callback(_background.discard)


async def synthesize(text: str, voice: PersonaVoice, language_id: str) -> bytes:
    """One-shot: the whole chunk as a single WAV. KugelAudio by default,
    DiReKT on failure or under DEBUG.

    KugelAudio wants the bare language code ("de", "en") here, not a full
    locale tag -- it rejects "de-DE"/"en-GB" with "Invalid request", which
    then degrades silently into the DiReKT fallback voice.
    """
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

    if not pcm:
        raise KugelAudioError("KugelAudio returned no audio")

    return _pcm16_to_wav(bytes(pcm), sample_rate)


async def _synthesize(text: str, voice: PersonaVoice) -> bytes:
    """DiReKT Voxtral batch call, one retry (ADR 0016)."""
    last_err: OpenAIError | None = None
    for attempt in range(2):
        try:
            # The persona's line rather than the user's words, so this is
            # generated content and not personal data — but it is still one
            # half of a recorded conversation, and a rule with an exception
            # is harder to keep than one without. Same switch.
            if LOG_TRANSCRIPTS:
                logger.info("Synthesizing via DiReKT TTS (%s, voice=%s): %r",
                            TTS_MODEL, voice.tts_voice, text)
            else:
                logger.info("Synthesizing via DiReKT TTS (%s, voice=%s, %d characters)",
                            TTS_MODEL, voice.tts_voice, len(text))
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


def duration_ms(wav_bytes: bytes) -> int:
    """Playback length of one synthesized chunk.

    Both backends deliver WAV -- KugelAudio's headerless PCM is wrapped above --
    so the header is always there to read. 0 for anything unreadable: the
    caller uses this to place the Persona on the Session's timeline (ADR 0051),
    which must not be able to fail a call.
    """
    try:
        with wave.open(io.BytesIO(wav_bytes)) as wav:
            return round(wav.getnframes() * 1000 / wav.getframerate())
    except (wave.Error, ZeroDivisionError, EOFError):
        logger.warning("Synthesized chunk has no readable WAV header; timing it as 0 ms")
        return 0
