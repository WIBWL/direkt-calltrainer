"""Dialogue-generation client calls."""

import logging
import re
from collections.abc import AsyncIterator

from openai import OpenAIError

from backend.clients.config import LLM_BACKEND, LLM_CLIENT, LLM_MODEL

logger = logging.getLogger("calltrainer")

_CLOSING_CLASSIFIER_PROMPT = (
    "This is a phone call transcript: \"assistant\" is the caller, \"user\" is "
    "the person they called. Does the user's LAST message signal that THIS "
    "PHONE CALL should end now — a farewell, or a request to postpone or "
    "continue it another time, another way, or with someone else — or a "
    "wrap-up with a specific answer, fix, or commitment (an actual action, "
    "amount, or timeframe) addressing the caller's concern?\n"
    "This is NOT about ending the call: the user just continuing the "
    "conversation; feedback on how the caller is talking (pace, detail, "
    "tone); or a vague reassurance with no specifics (\"ich kümmere mich "
    "darum\", \"ich stelle das klar\") that doesn't actually resolve anything.\n"
    "First, in one short sentence, name what the user's last message is "
    "actually doing. Then, on a new line, answer with exactly one word: "
    "\"yes\" or \"no\"."
)
_VERDICT_RE = re.compile(r"\b(yes|no|ja|nein)\b", re.IGNORECASE)

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
        # Without this the model can degenerate into repeating a sentence
        # within one reply (confirmed in testing).
        frequency_penalty=0.5,
        extra_body=extra_body,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta


async def signals_closing(messages: list[dict[str, str]]) -> bool:
    """Semantic check, given full context and a brief reasoning step: does
    the user's latest message signal ending/postponing the call itself?"""
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
            max_tokens=60,  # room for the one-sentence reasoning step, too
            extra_body=extra_body,
        )
    except OpenAIError as e:
        logger.error("Closing-signal check failed: %s", e)
        return False
    answer = response.choices[0].message.content or ""
    logger.info("Closing-signal check answered: %r", answer)
    # Last yes/no/ja/nein in the response, not a substring search over the
    # whole thing -- the reasoning sentence can itself quote the user's
    # words ("the user said 'ja', but...") without that being the verdict.
    verdicts = _VERDICT_RE.findall(answer)
    return bool(verdicts) and verdicts[-1].lower() in ("yes", "ja")
