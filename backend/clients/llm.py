"""Dialogue-generation client calls."""

import logging
from collections.abc import AsyncIterator

from openai import OpenAIError

from backend.clients.config import LLM_BACKEND, LLM_CLIENT, LLM_MODEL

logger = logging.getLogger("calltrainer")

_CLOSING_CLASSIFIER_PROMPT = (
    "This is a phone call transcript: \"assistant\" is the caller, \"user\" is "
    "the person they called. Answer with exactly one word, \"yes\" or \"no\": "
    "does the user's LAST message signal the call should end now, or be "
    "picked up another time — e.g. a farewell, a genuine wrap-up once the "
    "caller's concern is actually addressed, or a request to continue later? "
    "Answer \"no\" if it doesn't actually address or resolve what's being "
    "discussed, even if it sounds conclusive on its own."
)

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


async def signals_closing(messages: list[dict[str, str]]) -> bool:
    """Semantic check, given full context: does the user's latest message
    signal they want to end/postpone the call, or does it just sound like it?"""
    extra_body = {}
    if LLM_BACKEND == "efre":
        extra_body["chat_template_kwargs"] = {"enable_thinking": False}
    classifier_messages = [
        {"role": "system", "content": _CLOSING_CLASSIFIER_PROMPT},
        *messages[1:],  # skip the persona's own system prompt
    ]
    try:
        response = await LLM_CLIENT.chat.completions.create(
            model=LLM_MODEL,
            messages=classifier_messages,
            max_tokens=5,
            extra_body=extra_body,
        )
    except OpenAIError as e:
        logger.error("Closing-signal check failed: %s", e)
        return False
    answer = response.choices[0].message.content or ""
    return "yes" in answer.lower()
