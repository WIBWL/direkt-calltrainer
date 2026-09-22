"""What the user heard of a reply the server streamed ahead (ADR 0035).

The client reports how many milliseconds of the reply it played; the server
knows, per fully-synthesized chunk, where that chunk's audio ends and what
text it carried. `SpokenReply` keeps that record as the reply is voiced and
answers the one question a barge-in asks of it -- `cut(played_ms)`: every chunk
played to its end, plus a word-prefix of the one the user cut off, and what
was synthesized but never played.

The record and the arithmetic are one module because the bug this code has
had was in how the two met: a checkpoint is written only once a chunk is fully
synthesized, and measured against the finished ones alone, a barge-in during
the first sentence found nothing heard (ADR 0035's amendment). The pending
chunk is now part of the record's own answer rather than something each caller
has to remember to add.
"""

from dataclasses import dataclass

# The client's reported playback position and the server's summed WAV
# durations are independent clocks, so a sentence heard in full can land just
# short of its checkpoint. This slack absorbs that, and is the benefit of the
# doubt on the sentence the user cut off.
BARGE_IN_GRACE_MS = 300

# (audio ms at the chunk's end, the reply's text through that chunk, the chunk's own text)
Checkpoint = tuple[int, str, str]


@dataclass(frozen=True)
class Cut:
    """A reply cut short at a played position."""

    # What the user got: the Transcript and the model's history keep exactly this.
    heard: str
    # What had been synthesized and not yet played (F-51). Kept beside the
    # Transcript and never in the history: a model that read its own unspoken
    # sentence would carry on as though it had been said. Generation is
    # cancelled along with playback, so this is what had been synthesized, not
    # the whole sentence the model would eventually have produced.
    unheard: str


class SpokenReply:
    """One reply's voiced text and the audio behind it, as it is dispatched."""

    def __init__(self) -> None:
        self.text = ""
        # Audio ms dispatched so far.
        self.audio_ms = 0
        self._checkpoints: list[Checkpoint] = []

    def voice(self, text_chunk: str) -> None:
        """A chunk whose first audio has been produced: its words now count."""
        self.text += text_chunk + " "

    def add_audio(self, ms: int) -> None:
        """Audio of the current chunk has gone out to the client."""
        self.audio_ms += ms

    def finish_chunk(self, text_chunk: str) -> None:
        """The chunk is fully synthesized: record where its audio ends."""
        self._checkpoints.append((self.audio_ms, self.text.strip(), text_chunk.strip()))

    def cut(self, played_ms: int | None) -> Cut:
        """What was heard at `played_ms`, and what was not. `None` (an old
        client that sends no position) counts everything dispatched as heard."""
        heard = _heard_text(self._with_pending(), self.text, played_ms)
        remainder = self.text[len(heard):] if self.text.startswith(heard) else ""
        return Cut(heard=heard, unheard=remainder.strip())

    def _with_pending(self) -> list[Checkpoint]:
        """The checkpoints plus the chunk still being synthesized, if any.

        A checkpoint is written only when a chunk is *fully* synthesized, but
        its audio goes out sub-chunk by sub-chunk as KugelAudio produces it
        (ADR 0044) -- so the client is already playing the opening sentence
        while that sentence has no checkpoint. The pending entry ends at the
        audio actually dispatched, which is the honest span to measure a prefix
        against.
        """
        done = self._checkpoints[-1][1] if self._checkpoints else ""
        spoken = self.text.strip()
        pending = spoken[len(done):].strip()
        if not pending:
            return self._checkpoints
        return [*self._checkpoints, (self.audio_ms, spoken, pending)]


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


def _heard_text(checkpoints: list[Checkpoint], spoken_text: str, played_ms: int | None) -> str:
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
