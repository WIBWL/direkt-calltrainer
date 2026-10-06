"""What the user heard of a reply streamed ahead of playback (ADR 0035). The
pending chunk counts too, or a first-sentence barge-in would find nothing heard."""

from dataclasses import dataclass

# Client playback and summed WAV durations are separate clocks; the slack also
# gives the cut-off sentence the benefit of the doubt.
BARGE_IN_GRACE_MS = 300

# (audio ms at the chunk's end, reply text through it, the chunk's own text)
Checkpoint = tuple[int, str, str]


@dataclass(frozen=True)
class Cut:

    # The transcript and the history keep exactly this.
    heard: str
    # Synthesized but unplayed. Never in the history: a model reading its own
    # unspoken sentence carries on as if it had been said.
    unheard: str


class SpokenReply:
    def __init__(self) -> None:
        self.text = ""
        self.audio_ms = 0
        self._checkpoints: list[Checkpoint] = []

    def voice(self, text_chunk: str) -> None:
        self.text += text_chunk + " "

    def add_audio(self, ms: int) -> None:
        self.audio_ms += ms

    def finish_chunk(self, text_chunk: str) -> None:
        self._checkpoints.append((self.audio_ms, self.text.strip(), text_chunk.strip()))

    def cut(self, played_ms: int | None) -> Cut:
        """`None` counts everything dispatched as heard."""
        heard = _heard_text(self._with_pending(), self.text, played_ms)
        remainder = self.text[len(heard):] if self.text.startswith(heard) else ""
        return Cut(heard=heard, unheard=remainder.strip())

    def _with_pending(self) -> list[Checkpoint]:
        # A chunk's checkpoint is written once fully synthesized, but its audio
        # is already playing (ADR 0044).
        done = self._checkpoints[-1][1] if self._checkpoints else ""
        spoken = self.text.strip()
        pending = spoken[len(done):].strip()
        if not pending:
            return self._checkpoints
        return [*self._checkpoints, (self.audio_ms, spoken, pending)]


def spoken_prefix(text: str, fraction: float) -> str:
    """The leading `fraction` cut back to a word boundary; a half-spoken word is dropped."""
    text = text.strip()
    if fraction >= 1:
        return text
    if fraction <= 0:
        return ""
    cut = round(fraction * len(text))
    if cut < len(text) and not text[cut].isspace():
        return text[:cut].rpartition(" ")[0].rstrip()
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
