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

KugelAudio is the only speech output there is (ADR 0103). It had the gateway's
own model behind it as a fallback until then (ADR 0040), which meant a dead
KugelAudio produced a call in a different voice, 2-3x slower, and a boot log
that said nothing was wrong. A failure now ends the Turn, which is the honest
answer and the one an operator notices.

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

*Both* paths: the one-shot one did not, for a while -- and that is the harder
of the two to notice, since the abandoned request's frames simply sit on the
shared socket and reach the *next call in the process*.

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

from backend.clients.config import KUGELAUDIO_CLIENT, KUGELAUDIO_MODEL, LOG_TRANSCRIPTS
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

    Raises `KugelAudioError` on any failure, before or after the first piece:
    there is nothing else to ask (ADR 0103), and re-synthesising after a
    partial reply would diverge from audio the user has already heard
    (ADR 0033). The caller ends the Turn.
    """
    # Spoken form, not written: German writes "1.400" and "6. Juli" with a
    # full stop that both the chunker and the TTS read as a sentence end.
    # Done here so the Transcript keeps the digits.
    text = for_speech(text, language_id)
    # Behind the switch: the Persona's line is generated rather than spoken by
    # anybody, but it is one half of a recorded conversation and routinely
    # carries the name and the facts the user has just said. This line ran
    # unconditionally while `config.py` promised that with the switch off "the
    # pipeline logs how long an utterance was and nothing about what was in
    # it" -- and it fires per chunk, so it wrote the whole Persona side of
    # every call into a file no deletion path reaches (ADR 0066).
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
    """One-shot: the whole chunk as a single WAV.

    On the same pooled connection as the streaming path and through the same
    `_pooled_request`, so it carries the same two guards. It once had neither,
    and that was the harder of the two to notice (module docstring).

    KugelAudio wants the bare language code ("de", "en") here, not a full
    locale tag -- it rejects "de-DE"/"en-GB" with "Invalid request", which used
    to degrade silently into the fallback voice and now fails outright.
    """
    # Spoken form, not written: German writes "1.400" and "6. Juli" with a
    # full stop that both the chunker and the TTS read as a sentence end.
    # Done here so the Transcript keeps the digits.
    text = for_speech(text, language_id)
    # Same switch as the streaming path above, for the same reason.
    if LOG_TRANSCRIPTS:
        logger.info("Synthesizing via KugelAudio (%s, voice=%s, language=%s): %r",
                    KUGELAUDIO_MODEL, voice.kugelaudio_voice_id, language_id, text)
    else:
        logger.info("Synthesizing via KugelAudio (%s, voice=%s, language=%s, %d characters)",
                    KUGELAUDIO_MODEL, voice.kugelaudio_voice_id, language_id, len(text))
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

    KugelAudio's headerless PCM is wrapped above, so the header is always
    there to read. 0 for anything unreadable: the
    caller uses this to place the Persona on the Session's timeline (ADR 0051),
    which must not be able to fail a call.
    """
    try:
        with wave.open(io.BytesIO(wav_bytes)) as wav:
            return round(wav.getnframes() * 1000 / wav.getframerate())
    except (wave.Error, ZeroDivisionError, EOFError):
        logger.warning("Synthesized chunk has no readable WAV header; timing it as 0 ms")
        return 0
