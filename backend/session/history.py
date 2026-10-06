"""The call's message record; holds only what the user heard (ADR 0035)."""

from __future__ import annotations

Message = dict[str, str]

_USER = "user"
_REPLY = "assistant"


class History:
    def __init__(self, system_prompt: str):
        self._messages: list[Message] = [{"role": "system", "content": system_prompt}]

    @property
    def messages(self) -> list[Message]:
        return [dict(m) for m in self._messages]

    def system(self) -> Message:
        return self._messages[0]

    def recent(self, count: int) -> list[Message]:
        return self._messages[1:][-count:]

    def add_question(self, text: str) -> None:
        self._messages.append({"role": _USER, "content": text})

    def extend_question(self, text: str) -> None:
        # Only after a barge-in dropped the reply, so the question is last.
        self._messages[-1]["content"] = text

    def add_reply(self, text: str) -> None:
        self._messages.append({"role": _REPLY, "content": text})

    def last_reply_is(self, text: str) -> bool:
        last = self._messages[-1]
        return last["role"] == _REPLY and last["content"] == text

    def revise_reply(self, text: str) -> None:
        self._messages[-1]["content"] = text

    def drop_reply(self) -> None:
        self._messages.pop()

    def replies(self) -> list[str]:
        return [m["content"] for m in self._messages if m["role"] == _REPLY]

    def previous_reply(self) -> str:
        for message in reversed(self._messages):
            if message["role"] == _REPLY:
                return message["content"]
        return ""
