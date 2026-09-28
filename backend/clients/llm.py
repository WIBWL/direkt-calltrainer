"""Dialogue generation: the persona's reply, streamed token by token.

One backend, no fallback (ADR 0011, ADR 0103); streaming lets audio start before
the reply finishes (ADR 0033). Sampling is Qwen3-on-vLLM specific and lives in
`_sampling_kwargs` (docs/research/model-parameters.md)."""

import logging
import re
import time
from collections.abc import AsyncIterator
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from backend.clients.config import LLM_CLIENT, LLM_MODEL

logger = logging.getLogger(__name__)

# What `complete_json` parses into: any pydantic model the caller names, handed
# back as that type rather than as a dict, so the caller keeps its own fields.
_Model = TypeVar("_Model", bound=BaseModel)

# In thinking mode the reasoning trace is delivered out-of-band as
# `reasoning_content` when the gateway runs a reasoning parser, and inline as a
# <think>...</think> block when it does not. Strip the inline form so a caller
# never has to know which deployment it is talking to.
_THINK_BLOCK_RE = re.compile(r"\s*<think>.*?</think>\s*", re.DOTALL)

# Upper bound on worst-case latency and cost per reply, not a target length:
# the system prompt already constrains replies to short, realistic sentences,
# and observed completion-token usage stays well within double digits. Kept
# tight-ish because every extra token the model rambles is extra TTS work on
# the critical path -- a runaway reply is the main way a Turn gets slow.
_MAX_REPLY_TOKENS = 180


def _sampling_kwargs(
    *, think: bool, qwen_sampling: bool, presence_penalty: float | None
) -> dict[str, object]:
    """The parts of a request that belong to the model rather than to the call.

    Thinking must be off for a spoken reply (Qwen3's `chat_template_kwargs`): left on,
    `max_tokens` goes into a trace `delta.content` never surfaces. The rest is Qwen3
    tuning (ADR 0038); re-measure on a model change (docs/research/model-parameters.md)."""
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
    """Stream the persona's reply as it's generated, one token delta at a time.

    `retries` overrides the client's retry count; the boot check passes 0 so a
    rate-limited model reports as a 429, not as its probe's deadline expiring."""
    started = time.monotonic()
    client = LLM_CLIENT if retries is None else LLM_CLIENT.with_options(max_retries=retries)
    stream = await client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        stream=True,
        max_tokens=_MAX_REPLY_TOKENS,
        # Qwen3's documented non-thinking sampling. Unset, the vLLM default is
        # temperature/top_p 1.0, which measurably drifts off-persona and
        # off-task and rambles longer (slower). See docs/model-parameters.md.
        temperature=0.7,
        top_p=0.8,
        # Thinking off, and presence_penalty 1.5 -- Qwen3's recommended
        # anti-repetition knob, which beat frequency_penalty 0.5 in cross-Turn
        # tests. See `_sampling_kwargs`; the in-code guard (ADR 0038) backstops
        # it either way.
        **_sampling_kwargs(think=False, qwen_sampling=True, presence_penalty=1.5),
    )
# Time to first token, logged per Turn: it moves with the model or its thinking
# level, and a reply that thinks before speaking looks just like a slow network.
    first = True
    async for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            if first:
                first = False
                logger.info("LLM first token after %.2f s (%s)", time.monotonic() - started, LLM_MODEL)
            yield delta


# The wrap-up is a whole document, generated in thinking mode, so this covers the
# trace too; running out inside the trace yields no answer. Capped rather than
# None so a repetition loop cannot run to the RQ job timeout.
_MAX_FEEDBACK_TOKENS = 4000

# Its own read timeout: the client-wide TIMEOUT bounds the gap between streamed
# chunks, but this call is not streamed, and 4000 tokens plus a trace on the 4B
# model takes minutes. Kept below `queue.JOB_TIMEOUT_S` (300 s, not imported: no
# dependency on the queue) so the request fails inside the job and is recorded.
_FEEDBACK_TIMEOUT_S = 240.0


async def complete(
    messages: list[dict[str, str]],
    *,
    max_tokens: int | None = _MAX_FEEDBACK_TOKENS,
    think: bool = False,
    retries: int | None = None,
) -> str:
    """One non-streamed completion off the live path: wrap-up (ADR 0049), document
    summary (F-58), follow-up draft (F-60). `max_tokens=None` leaves only the context
    window as a bound; `think=True` is slower but writes markedly better (the wrap-up's
    German needs it); `retries` as in `stream_reply`. Same model as the reply (ADR 0103)."""
    # This path is reached only from the worker, so the log line is the one
    # place its parameters are ever visible. `stream_reply` logs its own.
    logger.info("LLM completion (%s, max_tokens=%s, think=%s)...", LLM_MODEL, max_tokens, think)
    client = LLM_CLIENT if retries is None else LLM_CLIENT.with_options(max_retries=retries)
    completion = await client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        # Per request, overriding the client's own: see _FEEDBACK_TIMEOUT_S.
        timeout=_FEEDBACK_TIMEOUT_S,
        **({"max_tokens": max_tokens} if max_tokens is not None else {}),
        # Thinking mode: Qwen3's documented sampling for it (a low temperature
        # there degrades into repetition). Non-thinking: low but not zero, so the
        # output reads naturally while staying close to its input.
        temperature=0.6 if think else 0.3,
        **({"top_p": 0.95} if think else {}),
        **_sampling_kwargs(think=think, qwen_sampling=think, presence_penalty=None),
    )
    text = completion.choices[0].message.content or ""
    return _strip_reasoning(text) if think else text


def _strip_reasoning(text: str) -> str:
    """The answer out of a thinking-mode reply, or "" if there is no answer yet.

    An unclosed `<think>` means the budget ran out mid-reasoning. Never return the
    trace: it is full of `{`, and a JSON-scraping caller would take it as the answer.
    """
    stripped = _THINK_BLOCK_RE.sub("", text)
    if "<think>" in stripped:
        logger.warning("Reasoning trace did not close — the token budget ran out inside it")
        return ""
    return stripped.strip()


# --- Reading a structured reply -------------------------------------------
#
# JSON callers off the live path (wrap-up, follow-up draft, reverse briefing):
# a small model (ADR 0011) fences its output however plainly told not to.

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


# What a prompt asking for a JSON object has to forbid, word for word the same
# wherever one does: the follow-up draft (F-60) and the reverse briefing (F-61)
# carried two copies until they were found to be identical. Kept beside the
# parser whose failures each rule prevents -- N2 above all, since one unescaped
# double quote makes the whole answer unreadable to `json_object`.
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
    """The JSON object out of whatever the model wrapped it in. ValueError if
    there is none — a cue to retry or fall back, not an error worth a
    traceback."""
    fenced = _FENCE_RE.search(raw)
    candidate = fenced.group(1) if fenced else raw
    start, end = candidate.find("{"), candidate.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in the response")
    return candidate[start:end + 1]


def without_fenced_blocks(raw: str) -> str:
    """`raw` with every fenced block removed, content and all — the prose, for a
    caller that has given up on parsing the reply."""
    return _FENCE_RE.sub("", raw)


async def complete_json(
    messages: list[dict[str, str]], model: type[_Model], what: str
) -> _Model | None:
    """One structured answer off the live path, retried once; None if neither parsed.

    Thinking mode and no token cap, since running out inside the trace yields no
    answer (see `_strip_reasoning`). Returns None rather than raising: what an
    unusable answer means is the caller's to decide (the reverse briefing: a 503)."""
    for attempt in range(2):  # initial attempt + one retry
        raw = await complete(messages, max_tokens=None, think=True)
        try:
            return model.model_validate_json(json_object(raw))
        except (ValidationError, ValueError) as e:
            logger.warning("%s did not validate (attempt %d): %s", what, attempt + 1, e)
    return None
