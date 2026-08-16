"""Dialogue-generation client call."""

import logging
from collections.abc import AsyncIterator

from backend.clients.config import LLM_BACKEND, LLM_CLIENT, LLM_MODEL

logger = logging.getLogger("calltrainer")

_MAX_REPLY_TOKENS = 300


async def stream_reply(messages: list[dict[str, str]]) -> AsyncIterator[str]:
    """Stream the persona's reply as it's generated, one token delta at a time."""
    logger.info("Generating persona reply via LLM (%s)...", LLM_MODEL)
    extra_body = {}
    if LLM_BACKEND == "efre":
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
