"""The gateway settings both processes need (ADR 0103)."""

import httpx
from openai import AsyncOpenAI

from shared.env import required

DIREKT_URL = required("DIREKT_URL")
DIREKT_API_KEY = required("DIREKT_API_KEY")

# The library default (600 s, two retries) let a wedged gateway hold a Turn for
# half an hour. The wrap-up passes its own longer timeout.
TIMEOUT = httpx.Timeout(120.0, connect=5.0)

CLIENT = AsyncOpenAI(base_url=f"{DIREKT_URL}/v1", api_key=DIREKT_API_KEY, timeout=TIMEOUT)

LLM_CLIENT = CLIENT
LLM_MODEL = required("LLM_MODEL")
