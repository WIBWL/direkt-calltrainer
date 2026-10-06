"""Streamed LLM tokens into TTS-sized chunks (ADR 0033)."""

import re
from collections.abc import AsyncIterator

# A stop after a digit ("6. Juli", "1.400") is no sentence end; flushing there
# splits one sentence across two synthesis calls. speech_text.py removes it later.
_SENTENCE_END_RE = re.compile(r"(?<!\d)[.!?]\s*$")
# 80/250 sounded most natural in a listening test against 40/150 and 120/300.
_MIN_CHUNK_CHARS = 80
_MAX_CHUNK_CHARS = 250
# The first chunk sets the perceived latency, so it flushes past a lower floor
# (ADR 0044); still high enough that a bare "Ja." gets no TTS call of its own.
_FIRST_CHUNK_MIN_CHARS = 25


async def sentence_chunks(tokens: AsyncIterator[str]) -> AsyncIterator[str]:
    """The trailing partial sentence is always emitted."""
    buffer = ""
    is_first = True
    async for token in tokens:
        buffer += token
        min_chars = _FIRST_CHUNK_MIN_CHARS if is_first else _MIN_CHUNK_CHARS
        if len(buffer) >= _MAX_CHUNK_CHARS:
            split_at = buffer.rfind(" ")
            if split_at == -1:
                split_at = len(buffer)
            chunk, buffer = buffer[:split_at].strip(), buffer[split_at:].lstrip()
            if chunk:
                is_first = False
                yield chunk
        elif len(buffer) >= min_chars and _SENTENCE_END_RE.search(buffer):
            chunk, buffer = buffer.strip(), ""
            if chunk:
                is_first = False
                yield chunk
    remainder = buffer.strip()
    if remainder:
        yield remainder
