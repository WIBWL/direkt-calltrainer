"""Buffers streamed LLM tokens into TTS-sized chunks.

The seam the streaming pipeline (ADR 0033) turns on: regrouping the model's
tokens into sentence-sized pieces so each can be synthesised and start playing
while the rest of the reply is still generating.
"""

import re
from collections.abc import AsyncIterator

_SENTENCE_END_RE = re.compile(r"[.!?]\s*$")
# A listening test at 40/150, 80/250 and 120/300 chars found 80/250 most
# natural: smaller chunks were choppier (no prosody continuity into the next),
# larger ones only added latency before the first was ready.
_MIN_CHUNK_CHARS = 80
_MAX_CHUNK_CHARS = 250
# The first chunk sets the perceived latency of the whole Turn, so it flushes at
# the first sentence end past a much lower floor (ADR 0044) — ~200-300 ms sooner
# to the ear, worth the small prosody hit. The floor still stops a bare "Ja."
# from firing its own TTS call.
_FIRST_CHUNK_MIN_CHARS = 25


async def sentence_chunks(tokens: AsyncIterator[str]) -> AsyncIterator[str]:
    """Regroup LLM token deltas into synthesis-sized chunks, emitting each when
    complete. The trailing partial sentence is always emitted, so no text drops."""
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
