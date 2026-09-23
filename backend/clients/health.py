"""Startup health checks for the pipeline backends.

Fires one minimal real request at each backend (STT, LLM, TTS) so a dead model
surfaces at boot, not mid-call. Uses the exact prod code paths, including TTS's
KugelAudio-then-DiReKT fallback (see `SKIP_KUGELAUDIO` in
`backend.clients.config`).

Three checks and no more: the wrap-up runs on the same model as the spoken
reply, so the LLM check covers both.
"""

import asyncio
import contextlib
import io
import logging
import wave

from kugelaudio.exceptions import KugelAudioError
from openai import DEFAULT_MAX_RETRIES, OpenAIError

from backend.clients import llm, stt, tts
from backend.clients.config import (
    SKIP_KUGELAUDIO, KUGELAUDIO_MODEL, LLM_MODEL, STT_MODEL, TTS_MODEL,
)
from backend.personas import PersonaVoice

logger = logging.getLogger(__name__)

# The values a Session would use, kept as a literal rather than read from
# the Persona library: this checks whether the backends answer, and must
# not fail merely because the database is empty or unreachable (ADR 0041).
_CHECK_VOICE = PersonaVoice(tts_voice="de_male", kugelaudio_voice_id=1885)
_CHECK_LANGUAGE = "de"
_CHECK_TIMEOUT = 20.0
# One attempt, against the client's default of two retries. Retrying is right
# for a Turn -- a call should survive a blip -- and wrong here: the retries and
# their backoff run inside _CHECK_TIMEOUT, so a model answering 429 gets its
# answer thrown away and the probe reports the deadline instead. A liveness
# check that hides why it failed is worth less than one that fails honestly, and
# nothing downstream depends on this passing: it only logs.
#
# Only the LLM check takes it. STT and TTS go through clients this cannot
# reach from here -- the gateway one is shared with STT's own path, and
# KugelAudio is a different SDK entirely.
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
    """The backend that is actually configured, not whatever answers.

    `tts.synthesize` catches a KugelAudio failure and returns DiReKT audio, so
    checking through it reported "TTS OK (kugel-3)" while KugelAudio was dead --
    an expired key, say -- and the pilot then ran all day in the fallback voice,
    which is 2-3x slower (ADR 0040), with a green boot log and a zero exit code
    from scripts/check_backends.py. The check names KugelAudio, so it has to be
    KugelAudio that answered.
    """
    if SKIP_KUGELAUDIO:
        await tts.synthesize("Hallo.", _CHECK_VOICE, _CHECK_LANGUAGE)
        return
    # pylint: disable=protected-access  # no public one-shot that skips the fallback
    await tts._synthesize_kugelaudio("Hallo.", _CHECK_VOICE, _CHECK_LANGUAGE)


_CHECKS: dict[str, tuple] = {
    "STT": (_check_stt, STT_MODEL),
    "LLM": (_check_llm, LLM_MODEL),
    "TTS": (_check_tts, TTS_MODEL if SKIP_KUGELAUDIO else KUGELAUDIO_MODEL),
}


async def _run_check(name: str, check_fn, model: str) -> bool:
    try:
        await asyncio.wait_for(check_fn(), timeout=_CHECK_TIMEOUT)
    # Before OSError, which it is a subclass of -- and said in words, because
    # asyncio's TimeoutError carries no message: `str(e)` is empty and the line
    # used to end in a bare dash, which reads like a backend that answered with
    # nothing rather than one that did not answer. The retries are named in it
    # because they are the usual reason a *working* model lands here: the
    # OpenAI client retries a 429 or a 5xx with backoff before it raises, and
    # those attempts run inside this window, so a rate-limited model times out
    # here instead of reporting its 429.
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
        # `check_backends` promises never to raise, and `lifespan` calls it
        # without a try: anything escaping here would stop the app from booting
        # over a dead dependency, which is the opposite of what the promise is
        # for. The list above does not cover everything these round trips can
        # produce -- the TTS check runs through a third-party SDK that parses
        # server frames, so a non-JSON frame from a proxy error page is a
        # ValueError and nothing here would have caught it.
        logger.error("Startup check: %s FAILED (%s) — %s: %s",
                     name, model, type(e).__name__, str(e) or "no message")
        return False
    logger.info("Startup check: %s OK (%s)", name, model)
    return True


async def check_backends() -> bool:
    """Check every configured pipeline backend concurrently, one log line
    each; returns True only if all passed.

    Never raises — it runs from `lifespan`, which logs a dead dependency rather
    than failing the boot. The return value is for `scripts/check_backends.py`,
    which does exit non-zero on it.
    """
    results = await asyncio.gather(*(_run_check(name, check_fn, model) for name, (check_fn, model) in _CHECKS.items()))
    failing = results.count(False)
    if failing:
        logger.error("Startup check: %d of %d backends failing — calls will error until fixed", failing, len(results))
    else:
        logger.info("Startup check: all backends reachable")
    return failing == 0
