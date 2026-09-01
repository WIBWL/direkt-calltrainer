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
# The first chunk sets perceived latency for the whole Turn, so it is flushed
# at the first sentence end past a much lower floor: a shorter opening line
# reaches the ear sooner and the ~200-300 ms of TTS time saved matters more
# there than the small prosody hit. The floor still rules out a bare "Ja." /
# "Guten Tag." firing its own TTS call. Later chunks use _MIN_CHUNK_CHARS.
_FIRST_CHUNK_MIN_CHARS = 25


async def sentence_chunks(tokens: AsyncIterator[str]) -> AsyncIterator[str]:
    """Buffer streamed LLM tokens into TTS-sized chunks, so each chunk
    can go to TTS as soon as it's ready instead of waiting for the full reply."""
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
