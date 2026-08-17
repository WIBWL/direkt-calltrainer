"""Buffers streamed LLM tokens into TTS-sized chunks."""

import re
from collections.abc import AsyncIterator

_SENTENCE_END_RE = re.compile(r"[.!?]\s*$")
# A listening test comparing TTS output chunked at 40/150, 80/250, and 120/300
# chars (same text, same voice) found 80/250 sounded most natural.
# Smaller chunks were noticeably choppier (each chunk has no prosody/intonation
# continuity with the next), larger chunks didn't sound better but added latency.
_MIN_CHUNK_CHARS = 80
_MAX_CHUNK_CHARS = 250


async def sentence_chunks(tokens: AsyncIterator[str]) -> AsyncIterator[str]:
    """Buffer streamed LLM tokens into TTS-sized chunks, so each chunk
    can go to TTS as soon as it's ready instead of waiting for the full reply."""
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
