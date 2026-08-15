"""Clients and model/voice config for STT, LLM, and TTS — OpenAI-compatible by
default (EFRE-DiReKT/Gemini), with an optional non-OpenAI-compatible TTS
provider (KugelAudio) behind the TTS_BACKEND toggle."""

import os

from dotenv import load_dotenv
from kugelaudio import KugelAudio
from openai import AsyncOpenAI

load_dotenv()

# STT, LLM, and TTS all run behind the one university-hosted EFRE-DiReKT
# gateway (ADR 0011); which model handles each capability is a configuration
# concern (model name only), not a separate base URL (ADR 0018). Async client:
# these calls run inside async def routes, and a blocking sync client would
# freeze the event loop for the call's whole duration.
CLIENT = AsyncOpenAI(base_url=f"{os.environ['EFRE_URL']}/v1", api_key=os.environ["EFRE_API_KEY"])

STT_MODEL = os.environ["STT_MODEL"]
TTS_MODEL = os.environ["TTS_MODEL"]
TTS_VOICE = os.environ["TTS_VOICE"]

# Test-only escape hatch to run the dialogue-generation leg against Gemini's
# OpenAI-compatible endpoint instead of EFRE-DiReKT (set LLM_BACKEND=gemini in
# .env) — for comparing behavior/latency against a second real provider.
LLM_BACKEND = os.environ.get("LLM_BACKEND", "efre").lower()
if LLM_BACKEND == "gemini":
    LLM_CLIENT = AsyncOpenAI(base_url=os.environ["GEMINI_URL"], api_key=os.environ["GEMINI_API_KEY"])
    LLM_MODEL = os.environ["GEMINI_MODEL"]
else:
    LLM_CLIENT = CLIENT
    LLM_MODEL = os.environ["LLM_MODEL"]

# Same escape hatch for TTS: set TTS_BACKEND=kugelaudio in .env to synthesize
# via the KugelAudio SDK (not an OpenAI-compatible HTTP endpoint, hence its
# own client type) instead of EFRE-DiReKT. Always defined (None when unused)
# rather than conditionally, so importers don't trip static "possibly
# unbound" checks — backend/clients/tts.py only ever reads these when
# TTS_BACKEND == "kugelaudio", the same guard as here.
# pylint: disable=invalid-name
# Constants whose value comes from a call (KugelAudio(...), int(...)) rather
# than a literal/subscript throw off pylint's constant-vs-variable naming
# heuristic — these are still module-level config constants like the rest of
# this file, just conditionally populated.
TTS_BACKEND = os.environ.get("TTS_BACKEND", "efre").lower()
KUGELAUDIO_CLIENT = None
KUGELAUDIO_MODEL = None
KUGELAUDIO_VOICE_ID = None
if TTS_BACKEND == "kugelaudio":
    KUGELAUDIO_CLIENT = KugelAudio(api_key=os.environ["KUGELAUDIO_API_KEY"])
    KUGELAUDIO_MODEL = os.environ["KUGELAUDIO_MODEL"]
    KUGELAUDIO_VOICE_ID = int(os.environ["KUGELAUDIO_VOICE_ID"])
# pylint: enable=invalid-name
