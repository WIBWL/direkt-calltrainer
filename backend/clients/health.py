"""Startup health checks for the pipeline backends.

Fires one minimal real request at each backend (STT, LLM, TTS) through the prod
code paths, so a dead model surfaces at boot, not mid-call. One backend per leg
(ADR 0103); the LLM check covers the wrap-up too."""

import asyncio
import contextlib
import io
import logging
import wave

from kugelaudio.exceptions import KugelAudioError
from openai import DEFAULT_MAX_RETRIES, OpenAIError

from backend.clients import llm, stt, tts
from backend.clients.config import KUGELAUDIO_MODEL, LLM_MODEL, STT_MODEL
from backend.personas import PersonaVoice

logger = logging.getLogger(__name__)

# The values a Session would use, kept as a literal rather than read from
# the Persona library: this checks whether the backends answer, and must
# not fail merely because the database is empty or unreachable (ADR 0041).
_CHECK_VOICE = PersonaVoice(kugelaudio_voice_id=1885)
_CHECK_LANGUAGE = "de"
_CHECK_TIMEOUT = 20.0
# One attempt, not the client's default two retries: their backoff runs inside
# _CHECK_TIMEOUT, so a 429 would be reported as a timeout. Only the LLM check
# takes it; STT and TTS go through clients this cannot reach.
_CHECK_RETRIES = 0


def _silent_wav() -> bytes:
    """Half a second of silence — enough for the STT endpoint to accept."""
    buf = io.BytesIO()
    with wave.Wave_write(buf) as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 8000)
    return buf.getvalue()


async def _check_stt() -> None:
    await stt.transcribe(_silent_wav(), "healthcheck.wav", "audio/wav", _CHECK_LANGUAGE)


async def _check_llm() -> None:
    async with contextlib.aclosing(
        llm.stream_reply([{"role": "user", "content": "ping"}], retries=_CHECK_RETRIES)
    ) as stream:
        async for _ in stream:
            break  # one delta is enough to prove the model responds


async def _check_tts() -> None:
    """One real KugelAudio request, through the code path a call uses."""
    await tts.synthesize("Hallo.", _CHECK_VOICE, _CHECK_LANGUAGE)


_CHECKS: dict[str, tuple] = {
    "STT": (_check_stt, STT_MODEL),
    "LLM": (_check_llm, LLM_MODEL),
    "TTS": (_check_tts, KUGELAUDIO_MODEL),
}


async def _run_check(name: str, check_fn, model: str) -> bool:
    try:
        await asyncio.wait_for(check_fn(), timeout=_CHECK_TIMEOUT)
    # Before OSError, its superclass. Spelled out because asyncio's TimeoutError
    # has an empty message; the retries are named since a rate-limited model's
    # retried 429s run inside this window and end up here.
    except TimeoutError:
        logger.error(
            "Startup check: %s FAILED (%s) — no answer within %.0f s; a 429 or a 5xx is "
            "retried %d times inside that window and ends up looking like this",
            name, model, _CHECK_TIMEOUT, DEFAULT_MAX_RETRIES,
        )
        return False
    except (OpenAIError, KugelAudioError, OSError) as e:
        # Some of these carry no message either; the class name beats a blank.
        logger.error("Startup check: %s FAILED (%s) — %s", name, model, str(e) or type(e).__name__)
        return False
    except Exception as e:  # pylint: disable=broad-except  # see `check_backends`
        # `check_backends` promises never to raise and `lifespan` calls it without
        # a try. The TTS SDK parses server frames, so e.g. a proxy error page
        # surfaces as a ValueError the list above does not cover.
        logger.error("Startup check: %s FAILED (%s) — %s: %s",
                     name, model, type(e).__name__, str(e) or "no message")
        return False
    logger.info("Startup check: %s OK (%s)", name, model)
    return True


async def check_backends() -> bool:
    """Check every configured pipeline backend concurrently, one log line
    each; returns True only if all passed.

    Never raises: `lifespan` logs a dead dependency rather than failing the boot.
    """
    results = await asyncio.gather(*(_run_check(name, check_fn, model) for name, (check_fn, model) in _CHECKS.items()))
    failing = results.count(False)
    if failing:
        logger.error("Startup check: %d of %d backends failing — calls will error until fixed", failing, len(results))
    else:
        logger.info("Startup check: all backends reachable")
    return failing == 0
