"""One place where every pipeline-backend environment variable is read — once,
at import, into a module-level constant, never from inside a function elsewhere.

Required variables have no default and throw before the app can listen: a wrong
or missing value should fail now, not surface later as a 403 that looks like bad
credentials.

One backend per leg and no alternatives (ADR 0011, ADR 0103): STT and dialogue
generation run on the OpenAI-compatible gateway named here, speech output on
KugelAudio. Pointing the gateway somewhere else is an `.env` edit -- a URL, a
key and one model name per step -- not a switch in the code.
"""

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

# The library's own default is a 600-second read timeout and two retries, so a
# gateway that accepts the connection and then says nothing -- a wedged worker,
# no RST -- held a Turn for up to half an hour per leg while the user sat in
# "thinking" with no error and no way out. Nothing above these clients imposes a
# deadline: a Turn has none, and only the boot check wraps its calls in one.
#
# The read budget is per attempt and, on a stream, between chunks. Two minutes
# is far longer than any leg here actually takes -- the slowest measured
# first-token time is 3 s (docs/research/model-parameters.md) -- and short
# enough that a wedged backend surfaces as a failed Turn while the user is
# still in the call.
#
# "Between chunks" is why the wrap-up does not use it: that request is not
# streamed, so the *whole* document has to arrive inside the budget, and 4000
# tokens plus a thinking trace on a 4B model is minutes. `llm.complete` passes
# its own, longer one per request (`_FEEDBACK_TIMEOUT_S`) -- nothing is waiting
# on it, and cutting a wrap-up off at two minutes would be this constant
# breaking the thing it was added to protect.
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
