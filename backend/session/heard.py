"""What the user heard of a reply the server streamed ahead (ADR 0035).

The client reports how many milliseconds of the reply it played; the server
knows, per fully-synthesized chunk, where that chunk's audio ends and what
text it carried. This module turns the two into the text that was actually
heard: every chunk played to its end, plus a word-prefix of the one the user
cut off. Pure functions -- moved out of `orchestrator.py`, which sits at its
line ceiling, and unchanged in what they compute.
"""

# The client's reported playback position and the server's summed WAV
# durations are independent clocks, so a sentence heard in full can land just
# short of its checkpoint. This slack absorbs that, and is the benefit of the
# doubt on the sentence the user cut off.
BARGE_IN_GRACE_MS = 300

# (audio ms at the chunk's end, the reply's text through that chunk, the chunk's own text)
Checkpoint = tuple[int, str, str]


def spoken_prefix(text: str, fraction: float) -> str:
    """The leading `fraction` of `text` cut back to a word boundary -- what the
    user got of the sentence they cut off. Near-constant TTS rate maps playback
    time onto characters; a word still in the persona's mouth is not spoken."""
    text = text.strip()
    if fraction >= 1:
        return text
    if fraction <= 0:
        return ""
    cut = round(fraction * len(text))
    if cut < len(text) and not text[cut].isspace():
        return text[:cut].rpartition(" ")[0].rstrip()  # drop the half-spoken word
    return text[:cut].rstrip()


def heard_text(checkpoints: list[Checkpoint], spoken_text: str, played_ms: int | None) -> str:
    """The reply text the client heard. `None` (an old client that sends no
    position) falls back to everything dispatched."""
    if played_ms is None:
        return spoken_text.strip()
    budget = played_ms + BARGE_IN_GRACE_MS
    full = ""
    chunk_start = 0
    for chunk_end, cum_text, chunk_text in checkpoints:
        if budget >= chunk_end:
            full = cum_text
            chunk_start = chunk_end
            continue
        span = chunk_end - chunk_start
        partial = spoken_prefix(chunk_text, (budget - chunk_start) / span if span else 0.0)
        return f"{full} {partial}".strip() if full and partial else (full or partial)
    return full
