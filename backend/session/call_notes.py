"""The caller's notes on the call so far (ADR 0071, narrowed by ADR 0075).

The small model misread its own raw transcript, so it reads a five-line summary
in place of all but the last few exchanges. One background `llm.complete` per
exchange, never on the reply path; a failure keeps the stale notes.

The notes may only record what the user heard. A barge-in may trim a reply after
the notes were refreshed from all of it, and notes are rewritten from the previous
notes (ADR 0075), so every refresh for one exchange starts from the notes as they
stood before it (`_base`), and a reply dropped whole puts them back there."""

from __future__ import annotations

import asyncio
import logging

from openai import OpenAIError

from backend.clients import llm
from backend.personas import Persona
from backend.scenarios import Scenario
from backend.session.models import Turn
from backend.session.nudges import STATE_NOTES_FRAME
from backend.session.prompting import STATE_MAX_TOKENS, build_state_prompt

logger = logging.getLogger(__name__)


class CallNotes:
    """The notes of one call, refreshed in the background."""

    def __init__(self, persona: Persona, scenario: Scenario):
        # They name the caller and weigh the call against the Scenario's goal.
        self._persona = persona
        self._scenario = scenario
        self._text = ""
        self._task: asyncio.Task[None] | None = None
        # The notes before the exchange being summarised, and that exchange's
        # Turn (see the module docstring).
        self._base = ""
        self._turn: int | None = None

    @property
    def text(self) -> str:
        """The notes as they stand; empty until the first exchange completed."""
        return self._text

    def message(self) -> list[dict[str, str]]:
        """The system message the model reads them as, or nothing yet."""
        return [{"role": "system", "content": STATE_NOTES_FRAME + self._text}] if self._text else []

    def refresh(self, turn: Turn) -> None:
        """Summarise this Turn's exchange into the notes, in the background.

        Called when a reply is committed and again when a barge-in trims it, so
        a refresh still running for the same exchange is replaced."""
        if not turn.user_text or not turn.persona_text:
            return
        if self._turn != turn.seq:
            # First refresh for this exchange: today's notes are its base.
            self._base = self._text
            self._turn = turn.seq
        self._cancel()
        self._task = asyncio.create_task(self._summarise(turn.user_text, turn.persona_text))

    def discard(self, turn: Turn) -> None:
        """The reply was dropped whole (nothing of it was heard): no refresh may
        land for it, and the notes go back to what they said before it.

        Otherwise a refresh already in flight would write the unheard reply into
        the notes, with no later refresh to correct it."""
        if self._turn != turn.seq:
            return
        self._cancel()
        self._text = self._base
        self._turn = None

    async def settle(self) -> None:
        """Wait for a pending refresh. The live path never does; a test that
        asserts on the notes has to."""
        if self._task is not None:
            await asyncio.gather(self._task, return_exceptions=True)

    def close(self) -> None:
        """The Session is over: a refresh still in flight has no reader."""
        self._cancel()

    def _cancel(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()

    async def _summarise(self, user_text: str, persona_text: str) -> None:
        """One summarisation call.

        From `_base`, not from `_text`: on a re-run for the same exchange the
        latter may already hold the unheard part of the reply this run exists
        to take back out."""
        messages = build_state_prompt(self._base, user_text, persona_text, self._persona, self._scenario)
        try:
            notes = await llm.complete(messages, max_tokens=STATE_MAX_TOKENS)
        except (OpenAIError, TimeoutError, OSError) as e:
            logger.warning("Call-state notes not refreshed: %s", e)
            return
        except Exception:  # pylint: disable=broad-except  # a background task nobody awaits
            # Anything else would be swallowed until the garbage collector
            # reports it as an unretrieved task exception, long after the call
            # (ADR 0055). The notes are optional; the log line is not.
            logger.exception("Call-state notes refresh raised")
            return
        if notes.strip():
            self._text = notes.strip()
