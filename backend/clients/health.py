"""Boot checks: one real request per leg through the production code paths (ADR 0103)."""

import asyncio
import contextlib
import io
import logging
import wave

from kugelaudio.exceptions import KugelAudioError
from openai import DEFAULT_MAX_RETRIES, OpenAIError

from shared.clients import llm
from shared.clients.config import LLM_MODEL
from backend.clients import stt, tts
from backend.clients.config import KUGELAUDIO_MODEL, STT_MODEL
from backend.personas import PersonaVoice

logger = logging.getLogger(__name__)

# A literal, so the check works with an empty or unreachable database.
_CHECK_VOICE = PersonaVoice(kugelaudio_voice_id=1885)
_CHECK_LANGUAGE = "de"
_CHECK_TIMEOUT = 20.0
# No retries: their backoff would make a 429 look like a timeout. LLM only.
_CHECK_RETRIES = 0


def _silent_wav() -> bytes:
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
            break


async def _check_tts() -> None:
    await tts.synthesize("Hallo.", _CHECK_VOICE, _CHECK_LANGUAGE)


_CHECKS: dict[str, tuple] = {
    "STT": (_check_stt, STT_MODEL),
    "LLM": (_check_llm, LLM_MODEL),
    "TTS": (_check_tts, KUGELAUDIO_MODEL),
}


async def _run_check(name: str, check_fn, model: str) -> bool:
    try:
        await asyncio.wait_for(check_fn(), timeout=_CHECK_TIMEOUT)
    # Before OSError, its superclass; asyncio's TimeoutError has no message.
    except TimeoutError:
        logger.error(
            "Startup check: %s FAILED (%s) — no answer within %.0f s; a 429 or a 5xx is "
            "retried %d times inside that window and ends up looking like this",
            name, model, _CHECK_TIMEOUT, DEFAULT_MAX_RETRIES,
        )
        return False
    except (OpenAIError, KugelAudioError, OSError) as e:
        logger.error("Startup check: %s FAILED (%s) — %s", name, model, str(e) or type(e).__name__)
        return False
    except Exception as e:  # pylint: disable=broad-except  # see `check_backends`
        # `check_backends` never raises; the TTS SDK can surface a ValueError.
        logger.error("Startup check: %s FAILED (%s) — %s: %s",
                     name, model, type(e).__name__, str(e) or "no message")
        return False
    logger.info("Startup check: %s OK (%s)", name, model)
    return True


async def check_backends() -> bool:
    """Concurrent, one log line each. Never raises: a dead model must not stop the boot."""
    results = await asyncio.gather(*(_run_check(name, check_fn, model) for name, (check_fn, model) in _CHECKS.items()))
    failing = results.count(False)
    if failing:
        logger.error("Startup check: %d of %d backends failing — calls will error until fixed", failing, len(results))
    else:
        logger.info("Startup check: all backends reachable")
    return failing == 0
