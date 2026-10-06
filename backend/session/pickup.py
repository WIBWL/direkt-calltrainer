"""When the Persona asks whether anybody is on the line (ADR 0110). The silence
is counted from the latest of: the accept, the last prompt's end, and the last
reported speech start, so a slow answer still being recorded is not talked over."""

from __future__ import annotations

from collections.abc import Sequence

from shared.turn import Turn

PROMPT_AFTER_MS = 4000


class PickupWatch:
    def __init__(self, prompts: Sequence[str], enabled: bool):
        # Disabled for a reverse: the Persona has already picked up.
        self._prompts = tuple(prompts) if enabled else ()
        self._said = 0
        self._speaking_ms: int | None = None

    def note_speaking(self, now_ms: int) -> None:
        self._speaking_ms = now_ms

    def delay_ms(self, turns: Sequence[Turn], now_ms: int, activated: bool) -> int | None:
        """0 if overdue; None if not accepted yet, answered, or prompts spent."""
        if not activated or self._said >= len(self._prompts):
            return None
        if any(turn.user_text for turn in turns):
            return None
        since = max((t.persona_end_ms for t in turns if t.persona_end_ms is not None), default=0)
        if self._speaking_ms is not None:
            since = max(since, self._speaking_ms)
        return max(0, since + PROMPT_AFTER_MS - now_ms)

    def is_prompt(self, reply: str) -> bool:
        """Also matches the heard part of a prompt the user talked over."""
        heard = reply.strip()
        return bool(heard) and any(line.startswith(heard) for line in self._prompts)

    def next_line(self) -> str:
        line = self._prompts[self._said]
        self._said += 1
        return line
