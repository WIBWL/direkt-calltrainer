"""Every pipeline-backend environment variable, read once at import.

Required variables have no default and throw before the app listens, not later
as a misleading 403. One backend per leg (ADR 0011, ADR 0103): STT and dialogue
on the OpenAI-compatible gateway, speech output on KugelAudio."""

import os

import httpx
from dotenv import load_dotenv
from kugelaudio import KugelAudio
from openai import AsyncOpenAI

load_dotenv()


def _required_env(name: str) -> str:
    """Read a variable that must be set, or throw. No default: a fallback that
    happens to look right just moves the failure to the first request."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required (see .env.example)")
    return value


# The model gateway (ADR 0011): any OpenAI-compatible endpoint, named in `.env`.
# A named constant because `lifespan` in app.py checks this same URL at boot.
DIREKT_URL = _required_env("DIREKT_URL")
DIREKT_API_KEY = _required_env("DIREKT_API_KEY")

# The library default (600 s read, two retries) let a wedged gateway hold a Turn
# for up to half an hour with no error. Two minutes per attempt (between chunks
# on a stream) is far above any measured leg and nothing else imposes a deadline.
# The wrap-up is not streamed and passes its own longer `_FEEDBACK_TIMEOUT_S`.
TIMEOUT = httpx.Timeout(120.0, connect=5.0)

CLIENT = AsyncOpenAI(base_url=f"{DIREKT_URL}/v1", api_key=DIREKT_API_KEY, timeout=TIMEOUT)

# STT config.
STT_CLIENT = CLIENT
STT_MODEL = _required_env("STT_MODEL")

# LLM config: the same client and the same model for the spoken reply and for
# everything written after the call (ADR 0103). There was a second model behind
# a switch for a while (ADR 0074) and no fallback either way; what is left is
# the name in `.env`, because which model runs is a deployment fact and one
# buried in Python is one nobody checks before wondering why a call feels slow.
LLM_CLIENT = CLIENT
LLM_MODEL = _required_env("LLM_MODEL")

# TTS config: KugelAudio, and nothing else (ADR 0103). region="eu" pins to
# api.eu.kugelaudio.com; the EU endpoint is used because the app is deployed in
# the EU (ADR 0020).
KUGELAUDIO_CLIENT = KugelAudio(api_key=_required_env("KUGELAUDIO_API_KEY"), region="eu")
KUGELAUDIO_MODEL = _required_env("KUGELAUDIO_MODEL")
