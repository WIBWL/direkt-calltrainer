"""The LLM client: the streamed live reply and the off-path completions (ADR 0103)."""

import logging
import re
import time
from collections.abc import AsyncIterator
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from shared.clients.config import LLM_CLIENT, LLM_MODEL

logger = logging.getLogger(__name__)

_Model = TypeVar("_Model", bound=BaseModel)

# The inline form of a reasoning trace, for gateways without a reasoning parser.
_THINK_BLOCK_RE = re.compile(r"\s*<think>.*?</think>\s*", re.DOTALL)

# A bound on a runaway reply, not a target: every extra token is TTS work on the
# critical path.
_MAX_REPLY_TOKENS = 180


def _sampling_kwargs(
    *, think: bool, qwen_sampling: bool, presence_penalty: float | None
) -> dict[str, object]:
    """Model-specific request parts. Thinking must be off for a spoken reply, or
    `max_tokens` is spent in a trace `delta.content` never shows. The rest is
    Qwen3 tuning (ADR 0038): re-measure on a model change."""
    return {
        **({"presence_penalty": presence_penalty} if presence_penalty is not None else {}),
        "extra_body": {
            "chat_template_kwargs": {"enable_thinking": think},
            **({"top_k": 20, "min_p": 0} if qwen_sampling else {}),
        },
    }


async def stream_reply(
    messages: list[dict[str, str]], *, retries: int | None = None
) -> AsyncIterator[str]:
    """`retries=0` lets the boot check report a 429 instead of a timeout."""
    started = time.monotonic()
    client = LLM_CLIENT if retries is None else LLM_CLIENT.with_options(max_retries=retries)
    stream = await client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        stream=True,
        max_tokens=_MAX_REPLY_TOKENS,
        # Qwen3's non-thinking sampling; the vLLM default (1.0) drifts and rambles.
        temperature=0.7,
        top_p=0.8,
        # presence_penalty, not frequency_penalty: it beat 0.5 freq. in cross-Turn tests.
        **_sampling_kwargs(think=False, qwen_sampling=True, presence_penalty=1.5),
    )
    first = True
    async for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            if first:
                first = False
                logger.info("LLM first token after %.2f s (%s)", time.monotonic() - started, LLM_MODEL)
            yield delta


# A cap so a repetition loop cannot run to the job timeout. Nothing off the live
# path thinks: the trace alone overran any budget that fits the context (ADR 0103).
_MAX_FEEDBACK_TOKENS = 4000

# Not streamed, so it needs its own read timeout; below the job's 300 s so the
# failure is recorded inside the job.
_FEEDBACK_TIMEOUT_S = 240.0


async def complete(
    messages: list[dict[str, str]],
    *,
    max_tokens: int | None = _MAX_FEEDBACK_TOKENS,
    think: bool = False,
    retries: int | None = None,
) -> str:
    """One non-streamed completion off the live path. `think=True` is unused on
    the current model (ADR 0103); measure before using it."""
    logger.info("LLM completion (%s, max_tokens=%s, think=%s)...", LLM_MODEL, max_tokens, think)
    client = LLM_CLIENT if retries is None else LLM_CLIENT.with_options(max_retries=retries)
    completion = await client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        timeout=_FEEDBACK_TIMEOUT_S,
        **({"max_tokens": max_tokens} if max_tokens is not None else {}),
        # Thinking mode needs its documented sampling; a low temperature degrades it.
        temperature=0.6 if think else 0.3,
        **({"top_p": 0.95} if think else {}),
        **_sampling_kwargs(think=think, qwen_sampling=think, presence_penalty=None),
    )
    text = completion.choices[0].message.content or ""
    return _strip_reasoning(text) if think else text


def _strip_reasoning(text: str) -> str:
    """The answer out of a thinking-mode reply, or "" while the trace is unclosed:
    the trace is full of `{` and would be taken for the JSON answer."""
    stripped = _THINK_BLOCK_RE.sub("", text)
    if "<think>" in stripped:
        logger.warning("Reasoning trace did not close — the token budget ran out inside it")
        return ""
    return stripped.strip()


# A small model fences its JSON however plainly told not to.

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


# One copy for every prompt asking for JSON (ADR 0100); one unescaped quote makes
# the answer unparseable.
JSON_ANSWER_NEVER = (
    "# Never\n"
    "N1. No markdown, no headings, no bullet characters, no line breaks "
    "inside the JSON strings.\n"
    "N2. No straight double quote inside a string: forget the backslash in "
    "front of one and the whole answer is unreadable. Use „ “ or single "
    "quotes.\n"
    "N3. No text of any kind before or after the JSON object.\n"
)


def json_object(raw: str) -> str:
    """The JSON object out of whatever wraps it; ValueError if there is none."""
    fenced = _FENCE_RE.search(raw)
    candidate = fenced.group(1) if fenced else raw
    start, end = candidate.find("{"), candidate.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in the response")
    return candidate[start:end + 1]


def without_fenced_blocks(raw: str) -> str:
    return _FENCE_RE.sub("", raw)


async def complete_json(
    messages: list[dict[str, str]], model: type[_Model], what: str
) -> _Model | None:
    """One structured answer, retried once; None if neither parsed. The caller
    decides what an unusable answer means."""
    for attempt in range(2):  # initial attempt + one retry
        raw = await complete(messages, max_tokens=None)
        try:
            return model.model_validate_json(json_object(raw))
        except (ValidationError, ValueError) as e:
            logger.warning("%s did not validate (attempt %d): %s", what, attempt + 1, e)
    return None
