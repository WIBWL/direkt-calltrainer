"""Dialogue-generation client call."""

import logging
from collections.abc import AsyncIterator

from backend.clients.config import LLM_BACKEND, LLM_CLIENT, LLM_MODEL

logger = logging.getLogger("calltrainer")

# Bounds worst-case reply length/latency; a few realistic phone sentences
# need nowhere near this many tokens.
_MAX_REPLY_TOKENS = 300


async def stream_reply(messages: list[dict[str, str]]) -> AsyncIterator[str]:
    """Stream the persona's reply as it's generated, one token delta at a time."""
    logger.info("Generating persona reply via LLM (%s)...", LLM_MODEL)
    extra_body = {}
    if LLM_BACKEND == "efre":
        # EFRE's model is a reasoning model that otherwise spends several
        # seconds (measured: ~5-30s, highly variable) "thinking" before the
        # first visible token — this cuts that dramatically (measured: down
        # to ~5-8s). Not a standard OpenAI field, so only send it to the
        # vLLM/LiteLLM-fronted EFRE backend — Gemini's OpenAI-compat layer
        # rejects unknown extra_body fields outright (400).
        extra_body["chat_template_kwargs"] = {"enable_thinking": False}
    stream = await LLM_CLIENT.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        stream=True,
        max_tokens=_MAX_REPLY_TOKENS,
        extra_body=extra_body,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta
