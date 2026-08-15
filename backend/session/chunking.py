"""Buffers streamed LLM tokens into TTS-sized chunks."""

import re
from collections.abc import AsyncIterator

_SENTENCE_END_RE = re.compile(r"[.!?]\s*$")
# Keep accumulating past a sentence boundary until at least this many chars
# are buffered, so a typical 2-3-short-sentence reply becomes one (or two)
# TTS calls instead of one per sentence — each independent TTS call has no
# prosody/intonation continuity with the next, which is what made replies
# sound choppy when synthesized one short sentence at a time. Only viable
# now that LLM generation itself is fast (see ADR 0026's Qwen3 switch) —
# waiting for more text used to cost real time when the LLM was the
# bottleneck; now TTS is, so fewer/larger chunks helps both naturalness and
# overall latency.
_MIN_CHUNK_CHARS = 80
_MAX_CHUNK_CHARS = 250  # hard cap regardless of sentence boundaries


async def sentence_chunks(tokens: AsyncIterator[str]) -> AsyncIterator[str]:
    """Buffer streamed LLM token deltas into TTS-sized chunks, so each chunk
    can go to TTS as soon as it's ready instead of waiting for the full reply
    (ADR 0026). Flushes at a sentence boundary once at least
    `_MIN_CHUNK_CHARS` has accumulated (grouping short sentences together for
    natural-sounding prosody), with a hard `_MAX_CHUNK_CHARS` fallback at the
    nearest word boundary for long unpunctuated runs."""
    buffer = ""
    async for token in tokens:
        buffer += token
        if len(buffer) >= _MAX_CHUNK_CHARS:
            split_at = buffer.rfind(" ")
            if split_at == -1:
                split_at = len(buffer)
            chunk, buffer = buffer[:split_at].strip(), buffer[split_at:].lstrip()
            if chunk:
                yield chunk
        elif len(buffer) >= _MIN_CHUNK_CHARS and _SENTENCE_END_RE.search(buffer):
            chunk, buffer = buffer.strip(), ""
            if chunk:
                yield chunk
    remainder = buffer.strip()
    if remainder:
        yield remainder
