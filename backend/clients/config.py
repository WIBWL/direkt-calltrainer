"""Model config for STT, LLM (both single-backend, no fallback) and TTS
(KugelAudio by default, the EFRE model as a fallback only)."""

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

# Forces TTS to always use the EFRE fallback instead of KugelAudio, e.g. for
# local testing without KugelAudio credentials.
DEBUG = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")

# STT config
STT_CLIENT = CLIENT
STT_MODEL = _required_env("STT_MODEL")

# LLM config
LLM_CLIENT = CLIENT
LLM_MODEL = _required_env("LLM_MODEL")

# TTS config: KugelAudio is the default; TTS_MODEL (EFRE) is only a
# fallback, used if KugelAudio fails or if DEBUG is set.
TTS_MODEL = _required_env("TTS_MODEL")
if DEBUG:
    KUGELAUDIO_CLIENT = None
    KUGELAUDIO_MODEL = None
else:
    # region="eu" pins to api.eu.kugelaudio.com — the pilot is hosted on the
    # Würzburg campus (ADR 0020), so the EU endpoint is the closest and cuts
    # round-trip latency on every synthesis call.
    KUGELAUDIO_CLIENT = KugelAudio(api_key=_required_env("KUGELAUDIO_API_KEY"), region="eu")
    KUGELAUDIO_MODEL = _required_env("KUGELAUDIO_MODEL")
