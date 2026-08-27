"""Startup health checks for the three pipeline backends.

Fires one minimal real request at each configured backend (STT, LLM, TTS) so a
dead model surfaces at boot instead of mid-call. Exercises the exact prod code
paths in `stt` / `llm` / `tts`, including whichever provider each *_BACKEND
toggle selects.
"""

import asyncio
import contextlib
import io
import logging
import wave

from kugelaudio.exceptions import KugelAudioError
from openai import OpenAIError

from backend.clients import llm, stt, tts
from backend.clients.config import LLM_MODEL, STT_MODEL, TTS_MODEL
from backend.personas import PERSONAS

logger = logging.getLogger("calltrainer")

# Real persona voice/language, so the TTS check uses values a session would.
_CHECK_VOICE = PERSONAS[0].voice
_CHECK_LANGUAGE = "de"
_CHECK_TIMEOUT = 20.0


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
    async with contextlib.aclosing(llm.stream_reply([{"role": "user", "content": "ping"}])) as stream:
        async for _ in stream:
            break  # one delta is enough to prove the model responds


async def _check_tts() -> None:
    await tts.synthesize("Hallo.", _CHECK_VOICE, _CHECK_LANGUAGE)


_CHECKS: dict[str, tuple] = {
    "STT": (_check_stt, STT_MODEL),
    "LLM": (_check_llm, LLM_MODEL),
    "TTS": (_check_tts, TTS_MODEL),
}


async def _run_check(name: str, check_fn, model: str) -> bool:
    try:
        await asyncio.wait_for(check_fn(), timeout=_CHECK_TIMEOUT)
    except (OpenAIError, KugelAudioError, TimeoutError, OSError) as e:
        logger.error("Startup check: %s FAILED (%s) — %s", name, model, e)
        return False
    logger.info("Startup check: %s OK (%s)", name, model)
    return True


async def check_backends() -> bool:
    """Check all three pipeline backends concurrently. Logs one line per
    backend; returns True only if every check succeeded. Never raises."""
    results = await asyncio.gather(*(_run_check(name, check_fn, model) for name, (check_fn, model) in _CHECKS.items()))
    failing = results.count(False)
    if failing:
        logger.error("Startup check: %d of %d backends failing — calls will error until fixed", failing, len(results))
    else:
        logger.info("Startup check: all backends reachable")
    return failing == 0
