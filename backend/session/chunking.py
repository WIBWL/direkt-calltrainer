"""Buffers streamed LLM tokens into TTS-sized chunks."""

import re
from collections.abc import AsyncIterator

_SENTENCE_END_RE = re.compile(r"[.!?]\s*$")
_MAX_CHUNK_CHARS = 200


async def sentence_chunks(tokens: AsyncIterator[str]) -> AsyncIterator[str]:
    """Buffer streamed LLM token deltas into sentence/clause-sized chunks, so
    each chunk can go to TTS as soon as it's ready instead of waiting for the
    full reply (ADR 0026). Splits on sentence-ending punctuation, with a
    max-length fallback at the nearest word boundary for long unpunctuated
    runs."""
    buffer = ""
    async for token in tokens:
        buffer += token
        if _SENTENCE_END_RE.search(buffer):
            chunk, buffer = buffer.strip(), ""
            if chunk:
                yield chunk
        elif len(buffer) >= _MAX_CHUNK_CHARS:
            split_at = buffer.rfind(" ")
            if split_at == -1:
                split_at = len(buffer)
            chunk, buffer = buffer[:split_at].strip(), buffer[split_at:].lstrip()
            if chunk:
                yield chunk
    remainder = buffer.strip()
    if remainder:
        yield remainder
