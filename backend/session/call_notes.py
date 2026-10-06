"""The caller's notes on the call so far (ADR 0071), refreshed in the background.
Each refresh for one exchange starts from the notes before it (`_base`), so a
barge-in trim can take the unheard part back out."""

from __future__ import annotations

import asyncio
import logging

from openai import OpenAIError

from shared.clients import llm
from shared.turn import Turn
from backend.personas import Persona
from backend.scenarios import Scenario
from backend.session.nudges import STATE_NOTES_FRAME
from backend.session.prompting import STATE_MAX_TOKENS, build_state_prompt

logger = logging.getLogger(__name__)


class CallNotes:
    """The notes of one call, refreshed in the background."""

    def __init__(self, persona: Persona, scenario: Scenario):
        self._persona = persona
        self._scenario = scenario
        self._text = ""
        self._task: asyncio.Task[None] | None = None
        self._base = ""
        self._turn: int | None = None

    @property
    def text(self) -> str:
        return self._text

    def message(self) -> list[dict[str, str]]:
        return [{"role": "system", "content": STATE_NOTES_FRAME + self._text}] if self._text else []

    def refresh(self, turn: Turn) -> None:
        """Called on commit and again after a barge-in trim, replacing the first run."""
        if not turn.user_text or not turn.persona_text:
            return
        if self._turn != turn.seq:
            self._base = self._text
            self._turn = turn.seq
        self._cancel()
        self._task = asyncio.create_task(self._summarise(turn.user_text, turn.persona_text))

    def discard(self, turn: Turn) -> None:
        """The reply was dropped whole: cancel its refresh and restore the base."""
        if self._turn != turn.seq:
            return
        self._cancel()
        self._text = self._base
        self._turn = None

    async def settle(self) -> None:
        """Tests only; the live path never waits."""
        if self._task is not None:
            await asyncio.gather(self._task, return_exceptions=True)

    def close(self) -> None:
        self._cancel()

    def _cancel(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()

    async def _summarise(self, user_text: str, persona_text: str) -> None:
        # From `_base`: a re-run must not build on the unheard part it removes.
        messages = build_state_prompt(self._base, user_text, persona_text, self._persona, self._scenario)
        try:
            notes = await llm.complete(messages, max_tokens=STATE_MAX_TOKENS)
        except (OpenAIError, TimeoutError, OSError) as e:
            logger.warning("Call-state notes not refreshed: %s", e)
            return
        except Exception:  # pylint: disable=broad-except  # a background task nobody awaits
            # A background task nobody awaits: log it, or it vanishes.
            logger.exception("Call-state notes refresh raised")
            return
        if notes.strip():
            self._text = notes.strip()
