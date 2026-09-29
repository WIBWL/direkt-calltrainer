"""When the Persona asks whether anybody is on the line (ADR 0102).

In an ordinary call the Persona rang and the user answers first. A user who
accepts the call and then says nothing would otherwise hear nothing at all, for
as long as they cared to wait; a real caller says "Hallo?" after a few seconds,
and once more if that goes unanswered. This decides *when* -- the lines
themselves are the language pack's `pickup_prompts`, spoken by the
orchestrator.

The silence is counted from the latest of three moments: the call being
accepted (t=0 on the Session clock), the end of the Persona's last prompt, and
the last time the client reported the user starting to speak. The last one is
what keeps the Persona from asking "Hallo?" into a sentence the browser is
still recording: the audio reaches the server only once the user has finished,
so without the report a slow answer would be talked over. A report that turns
out to be a cough only postpones the prompt, which is the cheap direction to be
wrong in.
"""

from __future__ import annotations

from collections.abc import Sequence

from backend.session.models import Turn

# How long a silence after the pick-up is left before the Persona speaks into
# it. Long enough for someone to collect themselves and say their company and
# name, short enough that the line does not feel dead.
PROMPT_AFTER_MS = 4000


class PickupWatch:
    """The prompts one call has left, and when the next one is due."""

    def __init__(self, prompts: Sequence[str], enabled: bool):
        # Disabled for a reverse (ADR 0070): the user rang, the Persona picked
        # up and has already spoken.
        self._prompts = tuple(prompts) if enabled else ()
        self._said = 0
        self._speaking_ms: int | None = None

    def note_speaking(self, now_ms: int) -> None:
        """The client heard the user start to speak."""
        self._speaking_ms = now_ms

    def delay_ms(self, turns: Sequence[Turn], now_ms: int, activated: bool) -> int | None:
        """Milliseconds until the next prompt is due, 0 if it is overdue, or
        None if there is none to wait for: the call has not been accepted yet,
        the user has already answered, or every prompt has been said."""
        if not activated or self._said >= len(self._prompts):
            return None
        if any(turn.user_text for turn in turns):
            return None
        since = max((t.persona_end_ms for t in turns if t.persona_end_ms is not None), default=0)
        if self._speaking_ms is not None:
            since = max(since, self._speaking_ms)
        return max(0, since + PROMPT_AFTER_MS - now_ms)

    def is_prompt(self, reply: str) -> bool:
        """Whether a reply in the history is one of these prompts, or the part
        of one the user heard before talking over it. Never true in a reverse,
        which has none."""
        heard = reply.strip()
        return bool(heard) and any(line.startswith(heard) for line in self._prompts)

    def next_line(self) -> str:
        """The next prompt, which is then spent."""
        line = self._prompts[self._said]
        self._said += 1
        return line
