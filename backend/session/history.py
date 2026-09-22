"""The conversation as the model has been told it: the full record of one call.

A list of chat messages -- the system prompt, then the user's and the Persona's
lines in order -- which the orchestrator used to hold as a bare list and change
by index from seven places: `[-1]["content"] = ...` to extend a reopened
question, to append the fallback goodbye and to trim a reply to what was heard;
`.pop()` to drop a reply nobody heard; and a scan for `"assistant"` in four
readers. Every one of those was correct only because of where in a Turn it
ran. The operations are named here instead, and each says what it assumes.

What the *model* reads on a given Turn is not this -- it may be a window of it
plus the caller's notes (ADR 0071), and it carries a nudge that is never stored
(`nudges.py`). This is what the guards, the barge-in trims and the Transcript
work on (ADR 0035, ADR 0038), and it must only ever hold what the user heard.
"""

from __future__ import annotations

Message = dict[str, str]

_USER = "user"
_REPLY = "assistant"


class History:
    """The call's messages, oldest first, starting with the system prompt."""

    def __init__(self, system_prompt: str):
        self._messages: list[Message] = [{"role": "system", "content": system_prompt}]

    @property
    def messages(self) -> list[Message]:
        """A copy of the whole record. A copy, so a reader cannot rewrite it."""
        return [dict(m) for m in self._messages]

    def system(self) -> Message:
        """The system prompt's message."""
        return self._messages[0]

    def recent(self, count: int) -> list[Message]:
        """The last `count` messages after the system prompt."""
        return self._messages[1:][-count:]

    # -- The user's side ---------------------------------------------------

    def add_question(self, text: str) -> None:
        """A new user utterance."""
        self._messages.append({"role": _USER, "content": text})

    def extend_question(self, text: str) -> None:
        """Replace the open user utterance with its continued form. Only after a
        barge-in dropped the reply to it, so the question is still the last
        message."""
        self._messages[-1]["content"] = text

    # -- The Persona's side ------------------------------------------------

    def add_reply(self, text: str) -> None:
        """A reply the Persona committed to."""
        self._messages.append({"role": _REPLY, "content": text})

    def last_reply_is(self, text: str) -> bool:
        """Whether the record ends on exactly this reply -- the check a late
        revision makes before touching it, since a stale re-entry must not
        rewrite a message it no longer owns."""
        last = self._messages[-1]
        return last["role"] == _REPLY and last["content"] == text

    def revise_reply(self, text: str) -> None:
        """Replace the last reply: the fallback goodbye appended to it, or the
        part of it the user actually heard (ADR 0035)."""
        self._messages[-1]["content"] = text

    def drop_reply(self) -> None:
        """Take the last reply out: nothing of it was heard (ADR 0035)."""
        self._messages.pop()

    def replies(self) -> list[str]:
        """Every reply so far, oldest first; `[0]` is the opening line."""
        return [m["content"] for m in self._messages if m["role"] == _REPLY]

    def previous_reply(self) -> str:
        """The last reply, or "" before the first."""
        for message in reversed(self._messages):
            if message["role"] == _REPLY:
                return message["content"]
        return ""
