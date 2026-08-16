"""Buffers streamed LLM tokens into TTS-sized chunks."""

import re
from collections.abc import AsyncIterator

_SENTENCE_END_RE = re.compile(r"[.!?]\s*$")
_MIN_CHUNK_CHARS = 80
_MAX_CHUNK_CHARS = 250


async def sentence_chunks(tokens: AsyncIterator[str]) -> AsyncIterator[str]:
    """Buffer streamed LLM token deltas into TTS-sized chunks, so each chunk
    can go to TTS as soon as it's ready instead of waiting for the full reply.
    Flushes at a sentence boundary once at least `_MIN_CHUNK_CHARS` has
    accumulated (grouping short sentences together for natural-sounding
    prosody), with a hard `_MAX_CHUNK_CHARS` fallback at the nearest word
    boundary for long unpunctuated runs."""
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
