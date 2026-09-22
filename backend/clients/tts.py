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
before producing audio, or always under ``SKIP_KUGELAUDIO``.

**A stream left before its ``final`` frame poisons the pooled socket** (ADR
0044 amendment). ``stream_async`` sends the request on the shared connection
and reads frames until ``final`` -- with no request id to tell one request's
frames from the next. A barge-in closes the Turn generator mid-stream, so that
request's remaining audio *and* its ``final`` stay queued on the socket; the
next ``stream_async`` then yields that stale audio as its own, ends on the stale
``final``, and leaves its own frames for the call after it -- a one-chunk
offset that persists for the life of the connection. Live, that was the
persona's last sentence arriving at the start of the *next* Turn, every Turn,
once a call had been interrupted mid-sentence. So both paths drop the pooled
connection whenever they are left short of ``final`` and re-warm a fresh one
off the critical path (``kugelaudio==1.9.0`` has no public call for this;
``_close_ws_connection`` is the one it uses internally).

*Both* paths: the one-shot one did not, for a while. It falls back to DiReKT on
a mid-stream failure and therefore looks healthy -- the fallback-closing line
is simply spoken in the other voice -- while the abandoned request's frames sit
on the shared socket and reach the *next call in the process*.

**And one request at a time** (``_pool_lock``). The connection is a process-wide
singleton, so two Sessions synthesizing at once put two requests on one wire and
call ``recv()`` on it from two tasks. ``websockets`` answers the second with a
``ConcurrencyError``, which is a ``RuntimeError`` and matches none of the
handlers along the TTS path: one call ends on ``tts_failed`` and the other is
stored as an aborted Session and logged as a client that went away. ADR 0044
weighed the pooled connection against *successive* requests and called low
concurrency a cost argument; it is a correctness precondition, and this lock is
what supplies it. A chunk's synthesis is short and faster than the audio it
produces, so the wait is bounded by one sentence.
"""

import asyncio
import contextlib
import io
import logging
import wave
from collections.abc import AsyncIterator

from kugelaudio.exceptions import KugelAudioError
from kugelaudio.models import AudioChunk
from openai import OpenAIError

from backend.clients.config import (
    CLIENT,
    SKIP_KUGELAUDIO,
    KUGELAUDIO_CLIENT,
    KUGELAUDIO_MODEL,
    LOG_TRANSCRIPTS,
    TTS_MODEL,
)
from backend.clients.speech_text import for_speech
from backend.personas import PersonaVoice

logger = logging.getLogger(__name__)

# Held for the whole of one request on the pooled connection -- the send, every
# frame read back, and the drop-and-re-warm that follows an unfinished one. See
# the module docstring. Everything that touches `KUGELAUDIO_CLIENT.tts` takes
# it, and nothing takes it twice: `_drop_pooled_connection` is the lock-free
# half of the reset, called from inside a held lock.
_pool_lock = asyncio.Lock()


async def prewarm() -> None:
    """Open KugelAudio's pooled streaming connection ahead of the first Turn.

    Called once from the app's lifespan. `stream_async` (which
    `synthesize_stream` uses) reuses this connection, so the first synthesis
    of the process skips the ~300-600 ms TCP+TLS+WebSocket handshake. No-op
    under SKIP_KUGELAUDIO."""
    if SKIP_KUGELAUDIO or KUGELAUDIO_CLIENT is None:
        return
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

    Falls back to one DiReKT batch WAV if KugelAudio fails *before* producing any
    audio. Raises `KugelAudioError` if it fails *after* — a fresh synthesis
    would diverge from audio the user has already heard (ADR 0033), so the
    caller ends the Turn instead.
    """
    # Spoken form, not written: German writes "1.400" and "6. Juli" with a
    # full stop that both the chunker and the TTS read as a sentence end.
    # Done here so every backend and every fallback below gets it, and so
    # the Transcript keeps the digits.
    text = for_speech(text, language_id)
    if SKIP_KUGELAUDIO or KUGELAUDIO_CLIENT is None:
        yield await _synthesize(text, voice)
        return

    # Behind the switch, for the reason the DiReKT branch below states: the
    # Persona's line is generated rather than spoken by anybody, but it is one
    # half of a recorded conversation and routinely carries the name and the
    # facts the user has just said. This line ran unconditionally while
    # `config.py` promised that with the switch off "the pipeline logs how long
    # an utterance was and nothing about what was in it" -- and it fires per
    # chunk, so it wrote the whole Persona side of every call into a file no
    # deletion path reaches (ADR 0066).
    if LOG_TRANSCRIPTS:
        logger.info(
            "Synthesizing (streaming) via KugelAudio (%s, voice=%s, language=%s): %r",
            KUGELAUDIO_MODEL, voice.kugelaudio_voice_id, language_id, text,
        )
    else:
        logger.info(
            "Synthesizing (streaming) via KugelAudio (%s, voice=%s, language=%s, %d characters)",
            KUGELAUDIO_MODEL, voice.kugelaudio_voice_id, language_id, len(text),
        )
    produced = False
    fallback = None
    try:
        async with contextlib.aclosing(_pooled_request(text, voice, language_id)) as chunks:
            async for chunk in chunks:
                produced = True
                yield _pcm16_to_wav(chunk.audio, chunk.sample_rate)
    except (KugelAudioError, TimeoutError, OSError) as e:
        if produced:
            raise KugelAudioError(f"KugelAudio stream failed after producing audio: {e}") from e
        logger.warning("KugelAudio streaming failed before any audio, falling back to DiReKT: %s", e)
        # Synthesized after the request has let go of the connection: DiReKT
        # is a different backend and has no business holding KugelAudio's.
        fallback = text
    if fallback is not None:
        yield await _synthesize(fallback, voice)


async def _pooled_request(text: str, voice: PersonaVoice, language_id: str) -> AsyncIterator[AudioChunk]:
    """One request on the pooled KugelAudio connection, and the only way onto it.

    Both guards the module docstring describes live here, once, for both
    callers: the lock is held for the whole request -- across the yields, on
    purpose, since the connection is in use until `final` and a second Session
    sending meanwhile is the `ConcurrencyError` -- and any exit short of the
    `final` frame drops the socket and re-warms a fresh one. They were written
    out twice, and the one-shot path went without them for a while.

    Consume it under `contextlib.aclosing`: a caller that stops early (a
    barge-in closing the stream) must reach the `finally` below *now*, not when
    the garbage collector gets round to it, or the next request reads this
    one's frames.
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

    Call with `_pool_lock` held -- it is the pooled connection this closes, and
    the re-warm it schedules takes the lock for itself. The next chunk pays a
    cold handshake only if it arrives before that re-warm completes; after a
    barge-in that is the next *Turn*, seconds away."""
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
    DiReKT on failure or under SKIP_KUGELAUDIO.

    KugelAudio wants the bare language code ("de", "en") here, not a full
    locale tag -- it rejects "de-DE"/"en-GB" with "Invalid request", which
    then degrades silently into the DiReKT fallback voice.
    """
    # Spoken form, not written: German writes "1.400" and "6. Juli" with a
    # full stop that both the chunker and the TTS read as a sentence end.
    # Done here so every backend and every fallback below gets it, and so
    # the Transcript keeps the digits.
    text = for_speech(text, language_id)
    if not SKIP_KUGELAUDIO:
        try:
            return await _synthesize_kugelaudio(text, voice, language_id)
        except (KugelAudioError, TimeoutError, OSError) as e:
            logger.warning("KugelAudio TTS failed, falling back to DiReKT: %s", e)
    return await _synthesize(text, voice)


async def _synthesize_kugelaudio(text: str, voice: PersonaVoice, language_id: str) -> bytes:
    """The one-shot request, on the same pooled connection as the streaming one
    and through the same `_pooled_request`, so it carries the same two guards.
    It once had neither, and it is the harder of the two to notice --
    `synthesize` catches the failure and answers in the DiReKT voice, so the
    fallback-closing line is merely spoken differently while the abandoned
    request's frames wait on the socket for the next call in the process
    (module docstring)."""
    pcm = bytearray()
    sample_rate = 24000
    async with contextlib.aclosing(_pooled_request(text, voice, language_id)) as chunks:
        async for chunk in chunks:
            pcm += chunk.audio
            sample_rate = chunk.sample_rate

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
