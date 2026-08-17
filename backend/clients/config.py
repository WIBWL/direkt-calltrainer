"""Model config for STT, LLM, and TTS — OpenAI-compatible by
default (EFRE_URL/Gemini), with an optional non-OpenAI-compatible TTS
provider (KugelAudio) behind the TTS_BACKEND toggle."""

import os

from dotenv import load_dotenv
from kugelaudio import KugelAudio
from openai import AsyncOpenAI

load_dotenv()


def _required_env(name: str) -> str:
    """Reads a required environment variable."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable {name!r}. Copy .env.example to .env and fill in real values."
        )
    return value


CLIENT = AsyncOpenAI(base_url=f"{_required_env('EFRE_URL')}/v1", api_key=_required_env("EFRE_API_KEY"))

# STT config
STT_CLIENT = CLIENT
STT_MODEL = _required_env("STT_MODEL")

# LLM config
LLM_BACKEND = os.environ.get("LLM_BACKEND", "efre").lower()
if LLM_BACKEND == "gemini":
    LLM_CLIENT = AsyncOpenAI(base_url=_required_env("GEMINI_URL"), api_key=_required_env("GEMINI_API_KEY"))
    LLM_MODEL = _required_env("GEMINI_MODEL")
else:
    LLM_CLIENT = CLIENT
    LLM_MODEL = _required_env("LLM_MODEL")

# TTS config
TTS_BACKEND = os.environ.get("TTS_BACKEND", "efre").lower()
if TTS_BACKEND == "kugelaudio":
    TTS_CLIENT = KugelAudio(api_key=_required_env("KUGELAUDIO_API_KEY"))
    TTS_MODEL = _required_env("KUGELAUDIO_MODEL")
else:
    TTS_CLIENT = CLIENT
    TTS_MODEL = _required_env("TTS_MODEL")
