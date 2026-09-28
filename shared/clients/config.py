"""The model gateway's environment variables, read once at import: everything
both processes need to reach the LLM. STT and speech output are the live call's
alone and live in `backend/clients/config.py`.

Required variables have no default and throw before the app listens, not later
as a misleading 403. One backend per leg (ADR 0011, ADR 0103): STT and dialogue
on the OpenAI-compatible gateway, speech output on KugelAudio."""

import httpx
from openai import AsyncOpenAI

from shared.env import required

# The model gateway (ADR 0011): any OpenAI-compatible endpoint.
# A named constant because `lifespan` in app.py checks this same URL at boot.
DIREKT_URL = required("DIREKT_URL")
DIREKT_API_KEY = required("DIREKT_API_KEY")

# The library default (600 s read, two retries) let a wedged gateway hold a Turn
# for up to half an hour with no error. Two minutes per attempt (between chunks
# on a stream) is far above any measured leg and nothing else imposes a deadline.
# The wrap-up is not streamed and passes its own longer `_FEEDBACK_TIMEOUT_S`.
TIMEOUT = httpx.Timeout(120.0, connect=5.0)

CLIENT = AsyncOpenAI(base_url=f"{DIREKT_URL}/v1", api_key=DIREKT_API_KEY, timeout=TIMEOUT)

# LLM config: the same client and the same model for the spoken reply and for
# everything written after the call (ADR 0103). There was a second model behind
# a switch for a while (ADR 0074) and no fallback either way; what is left is
# the name in `.env`, because which model runs is a deployment fact and one
# buried in Python is one nobody checks before wondering why a call feels slow.
LLM_CLIENT = CLIENT
LLM_MODEL = required("LLM_MODEL")
