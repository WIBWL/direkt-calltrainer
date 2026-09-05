"""One place where every pipeline-backend environment variable is read — once,
at import, into a module-level constant, never from inside a function elsewhere.

Required variables have no default and throw before the app can listen: a wrong
or missing value should fail now, not surface later as a 403 that looks like bad
credentials. STT and the LLM have one backend each, no fallback (ADR 0011); TTS
defaults to KugelAudio with the DiReKT model as fallback (ADR 0040), or the
DiReKT model always under DEBUG.
"""

import os

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


# The DiReKT model gateway (ADR 0011). A named constant because `lifespan` in
# app.py checks this same URL at boot.
DIREKT_URL = _required_env("DIREKT_URL")

CLIENT = AsyncOpenAI(base_url=f"{DIREKT_URL}/v1", api_key=_required_env("DIREKT_API_KEY"))

# Optional, default off. When truthy, TTS skips KugelAudio and uses the DiReKT
# model on every call — lets the app run without KugelAudio credentials.
DEBUG = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")

# STT config.
STT_CLIENT = CLIENT
STT_MODEL = _required_env("STT_MODEL")

# LLM config.
LLM_CLIENT = CLIENT
LLM_MODEL = _required_env("LLM_MODEL")

# TTS config: KugelAudio is the default; TTS_MODEL (the DiReKT model) is only the
# fallback, or always under DEBUG.
TTS_MODEL = _required_env("TTS_MODEL")
if DEBUG:
    # No KugelAudio client under DEBUG, so its credentials aren't required.
    KUGELAUDIO_CLIENT = None
    KUGELAUDIO_MODEL = None
else:
    # region="eu" pins to api.eu.kugelaudio.com; the EU endpoint is used because
    # the app is deployed in the EU (ADR 0020).
    KUGELAUDIO_CLIENT = KugelAudio(api_key=_required_env("KUGELAUDIO_API_KEY"), region="eu")
    KUGELAUDIO_MODEL = _required_env("KUGELAUDIO_MODEL")
