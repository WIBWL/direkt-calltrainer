"""Dialogue-generation client calls."""

import logging
from collections.abc import AsyncIterator

from backend.clients.config import LLM_CLIENT, LLM_MODEL

logger = logging.getLogger(__name__)

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
