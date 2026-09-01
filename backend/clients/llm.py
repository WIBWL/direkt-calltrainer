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


# The wrap-up is a whole document rather than one spoken line, so it needs a
# far larger budget than _MAX_REPLY_TOKENS -- and it is generated after the
# call, where latency costs nobody anything.
_MAX_FEEDBACK_TOKENS = 900


async def complete(messages: list[dict[str, str]]) -> str:
    """One non-streamed completion, for the post-call wrap-up (ADR 0046).

    Nothing is waiting on the first token here, unlike stream_reply, so the
    caller gets the finished text in one piece and can validate it as a whole.
    """
    logger.info("Generating feedback via LLM (%s)...", LLM_MODEL)
    completion = await LLM_CLIENT.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        max_tokens=_MAX_FEEDBACK_TOKENS,
        # Low but not zero: the wrap-up should read naturally, while staying
        # close to the findings it was given rather than embroidering them.
        temperature=0.3,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    return completion.choices[0].message.content or ""
