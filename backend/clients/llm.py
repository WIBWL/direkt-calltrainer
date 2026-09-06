"""Dialogue generation: the persona's reply, streamed token by token.

One backend, no fallback (ADR 0011). Streaming lets the orchestrator chunk the
reply and synthesise audio before it finishes (ADR 0033). The sampling
parameters below are Qwen3-specific, tuned by measurement (docs/model-parameters.md).
"""

import logging
import re
from collections.abc import AsyncIterator

from backend.clients.config import LLM_CLIENT, LLM_MODEL

logger = logging.getLogger(__name__)

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


async def stream_reply(messages: list[dict[str, str]]) -> AsyncIterator[str]:
    """Stream the persona's reply as it's generated, one token delta at a time."""
    logger.info("Generating persona reply via LLM (%s)...", LLM_MODEL)
    stream = await LLM_CLIENT.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        stream=True,
        max_tokens=_MAX_REPLY_TOKENS,
        # Qwen3's documented non-thinking sampling. Unset, the vLLM default is
        # temperature/top_p 1.0, which measurably drifts off-persona and
        # off-task and rambles longer (slower). See docs/model-parameters.md.
        temperature=0.7,
        top_p=0.8,
        # presence_penalty is Qwen3's recommended anti-repetition knob (the
        # card suggests 1.5 for endless repetitions); it beat frequency_penalty
        # 0.5 in cross-Turn repetition tests. The in-code guard (ADR 0038) still
        # backstops this.
        presence_penalty=1.5,
        extra_body={
            # Essential: with thinking on, first token takes ~3s and the whole
            # token budget is spent on (English) reasoning, leaving no reply.
            "chat_template_kwargs": {"enable_thinking": False},
            "top_k": 20,
            "min_p": 0,
        },
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta


# The wrap-up is a whole document rather than one spoken line, so it needs a
# far larger budget than _MAX_REPLY_TOKENS -- and it is generated after the
# call, where latency costs nobody anything.
# It runs in thinking mode, so this covers the trace as well as the answer;
# sized for the worst case, because running out inside the trace yields no
# answer at all. Capped rather than None so a repetition loop cannot run to the
# RQ job timeout.
_MAX_FEEDBACK_TOKENS = 4000


async def complete(
    messages: list[dict[str, str]],
    *,
    max_tokens: int | None = _MAX_FEEDBACK_TOKENS,
    think: bool = False,
) -> str:
    """One non-streamed completion — the post-call wrap-up (ADR 0049), the
    document summary for an authored Scenario (F-58) and the follow-up Scenario
    drafted from a Session's Feedback (F-60).

    Nothing is waiting on the first token here, unlike stream_reply, so the
    caller gets the finished text in one piece and can validate it as a whole.

    `max_tokens=None` leaves the output bounded only by the model's context
    window — the document summary uses it, because its own length rule is a
    character cap, not a token one, and thinking mode needs unpredictable room
    for its trace.

    `think=True` runs the model in reasoning mode: it is slower and spends part
    of the budget on a hidden trace, but extracts and writes markedly better.
    Only safe off the live path, where latency costs nobody anything and the
    reply is not streamed. All three callers use it: the document summary, the
    follow-up draft, and the wrap-up, whose German grammar breaks down without
    it.
    """
    logger.info(
        "LLM completion (%s, max_tokens=%s, think=%s)...", LLM_MODEL, max_tokens, think
    )
    completion = await LLM_CLIENT.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        **({"max_tokens": max_tokens} if max_tokens is not None else {}),
        # Thinking mode: Qwen3's documented sampling for it (a low temperature
        # there degrades into repetition). Non-thinking: low but not zero, so the
        # output reads naturally while staying close to its input.
        temperature=0.6 if think else 0.3,
        **({"top_p": 0.95} if think else {}),
        extra_body={
            "chat_template_kwargs": {"enable_thinking": think},
            **({"top_k": 20, "min_p": 0} if think else {}),
        },
    )
    text = completion.choices[0].message.content or ""
    return _strip_reasoning(text) if think else text


def _strip_reasoning(text: str) -> str:
    """The answer out of a thinking-mode reply, or "" if there is no answer yet.

    A `<think>` that never closes means the budget ran out mid-reasoning, so
    nothing after it was written. Returning the trace would be worse than
    returning nothing: it is full of `{`, and the wrap-up's caller scrapes JSON
    out of the reply, the model's deliberation would become its answer.
    """
    stripped = _THINK_BLOCK_RE.sub("", text)
    if "<think>" in stripped:
        logger.warning("Reasoning trace did not close — the token budget ran out inside it")
        return ""
    return stripped.strip()


# --- Reading a structured reply -------------------------------------------
#
# Two callers ask for JSON off the live path, the wrap-up (ADR 0049) and the
# follow-up draft (F-60), and a small model (ADR 0011) fences its output
# however plainly it is told not to. So the unwrapping lives here, once, next
# to the call that produced the text.

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


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
