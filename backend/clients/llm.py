"""Dialogue-generation client calls."""

import logging
from collections.abc import AsyncIterator

from backend.clients.config import LLM_CLIENT, LLM_MODEL

logger = logging.getLogger(__name__)

# Upper bound on worst-case latency and cost per reply, not a target length:
# the system prompt already constrains replies to short, realistic sentences,
# and observed completion-token usage stays well within double digits. This
# cap only matters if that constraint is ever violated (e.g. a degenerate
# repetition loop), so it's set generously above normal usage rather than
# tuned tightly against it.
_MAX_REPLY_TOKENS = 250


async def stream_reply(messages: list[dict[str, str]]) -> AsyncIterator[str]:
    """Stream the persona's reply as it's generated, one token delta at a time."""
    logger.info("Generating persona reply via LLM (%s)...", LLM_MODEL)
    stream = await LLM_CLIENT.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        stream=True,
        max_tokens=_MAX_REPLY_TOKENS,
        # Without this the model can degenerate into repeating a sentence
        # within one reply (confirmed in testing).
        frequency_penalty=0.5,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta
