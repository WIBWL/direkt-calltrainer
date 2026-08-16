"""Clients and model/voice config for STT, LLM, and TTS — OpenAI-compatible by
default (EFRE_URL/Gemini), with an optional non-OpenAI-compatible TTS
provider (KugelAudio) behind the TTS_BACKEND toggle."""

import os

from dotenv import load_dotenv
from kugelaudio import KugelAudio
from openai import AsyncOpenAI

load_dotenv()


def _required_env(name: str) -> str:
    """Reads a required env var, failing with a clear, actionable message
    instead of a bare KeyError traceback — this runs at import time, before
    app.py's own startup checks (e.g. its EFRE reachability check) ever get
    a chance to run."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable {name!r}. Copy .env.example to .env and fill in real values."
        )
    return value


CLIENT = AsyncOpenAI(base_url=f"{_required_env('EFRE_URL')}/v1", api_key=_required_env("EFRE_API_KEY"))

STT_MODEL = _required_env("STT_MODEL")

LLM_BACKEND = os.environ.get("LLM_BACKEND", "efre").lower()
if LLM_BACKEND == "gemini":
    LLM_CLIENT = AsyncOpenAI(base_url=_required_env("GEMINI_URL"), api_key=_required_env("GEMINI_API_KEY"))
    LLM_MODEL = _required_env("GEMINI_MODEL")
else:
    LLM_CLIENT = CLIENT
    LLM_MODEL = _required_env("LLM_MODEL")

TTS_BACKEND = os.environ.get("TTS_BACKEND", "efre").lower()
TTS_MODEL = None
# pylint: disable=invalid-name
# KUGELAUDIO_CLIENT's value comes from a call (KugelAudio(...)) rather than a
# literal, which throws off pylint's constant-vs-variable naming heuristic —
# it's still a module-level constant like the rest of this file.
KUGELAUDIO_CLIENT = None
KUGELAUDIO_MODEL = None
if TTS_BACKEND == "kugelaudio":
    KUGELAUDIO_CLIENT = KugelAudio(api_key=_required_env("KUGELAUDIO_API_KEY"))
    KUGELAUDIO_MODEL = _required_env("KUGELAUDIO_MODEL")
else:
    TTS_MODEL = _required_env("TTS_MODEL")
# pylint: enable=invalid-name
