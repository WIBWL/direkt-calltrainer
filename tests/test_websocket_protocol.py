"""The /ws/session wire protocol: handshake and event forwarding.

Covers:
  F-46  Live-Call-Interface (one WebSocket per session, state + audio frames)
  ADR 0033  streamed protocol: a JSON 'chunk' message then a raw binary frame
  ADR 0035  a 'turn.interrupt' control message is understood
  ADR 0041  the handshake resolves the ids through the database-backed
            library, faked here so the test needs no database
  Handshake robustness: a missing/!= 'session.start' or an unknown
  persona/scenario id closes the socket with protocol-error code 1002; a
  missing/invalid token closes with 1008 (F-50/ADR 0009).

starlette's TestClient can't be used here (the repo pins httpx 0.28, whose
Client rejects TestClient's `app=` kwarg), so the ASGI-level helpers are
driven directly through a fake WebSocket.
"""

import json

import pytest
from fastapi import WebSocketDisconnect

from backend.api import session_ws
from backend.session.models import AudioChunk, Failed, StateChanged, TurnCompleted
from tests.conftest import TEST_AUTH, TEST_PERSONAS, TEST_SCENARIOS

# session_ws's ASGI helpers are underscore-prefixed; driving them directly is
# the point of this module. `unused-argument`: a test takes `fake_library` only
# to activate the fixture.
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access
# pylint: disable=redefined-outer-name,unused-argument


@pytest.fixture(autouse=True)
def _accept_test_token(monkeypatch):
    """The real handshake verifies the token in `session.start`; here it's a
    stub. `test_handshake_rejects_a_missing_token` restores the real check."""
    monkeypatch.setattr(
        session_ws, "authenticate_ws", lambda msg: TEST_AUTH if msg.get("token") else None
    )


_START = {
    "type": "session.start",
    "token": "test",
    "persona_id": TEST_PERSONAS[0].id,
    "scenario_id": TEST_SCENARIOS[0].id,
}


class FakeWebSocket:
    def __init__(self, incoming=None):
        self._incoming = list(incoming or [])
        self.sent = []
        self.closed = None

    async def accept(self):
        pass

    async def receive_json(self):
        return self._next()

    async def receive_text(self):
        msg = self._next()
        return msg if isinstance(msg, str) else json.dumps(msg)

    async def receive_bytes(self):
        msg = self._next()
        assert isinstance(msg, (bytes, bytearray))
        return bytes(msg)

    def _next(self):
        if not self._incoming:
            raise WebSocketDisconnect(code=1000)
        item = self._incoming.pop(0)
        if item is _DISCONNECT:
            raise WebSocketDisconnect(code=1000)
        return item

    async def send_json(self, data):
        self.sent.append(data)

    async def send_bytes(self, data):
        self.sent.append(bytes(data))

    async def close(self, code=1000, reason=""):
        self.closed = (code, reason)


_DISCONNECT = object()


async def test_handshake_accepts_a_valid_session_start(fake_library):
    ws = FakeWebSocket([_START])
    result = await session_ws._handshake(ws)
    assert result == (TEST_PERSONAS[0], TEST_SCENARIOS[0], TEST_AUTH)
    assert ws.closed is None


async def test_handshake_rejects_a_wrong_first_message():
    ws = FakeWebSocket([{"type": "turn.audio.meta"}])
    assert await session_ws._handshake(ws) is None
    assert ws.closed[0] == 1002


async def test_handshake_rejects_a_missing_token():
    ws = FakeWebSocket([{k: v for k, v in _START.items() if k != "token"}])
    assert await session_ws._handshake(ws) is None
    assert ws.closed[0] == 1008  # policy violation


async def test_handshake_rejects_unknown_persona_or_scenario(fake_library):
    ws = FakeWebSocket([{**_START, "persona_id": "does-not-exist"}])
    assert await session_ws._handshake(ws) is None
    assert ws.closed[0] == 1002


async def test_handshake_handles_immediate_disconnect():
    ws = FakeWebSocket([_DISCONNECT])
    assert await session_ws._handshake(ws) is None


async def _events(*items):
    for it in items:
        yield it


async def test_forward_turn_events_maps_events_to_wire_messages():
    ws = FakeWebSocket()
    result = await session_ws._forward_turn_events(ws, _events(
        StateChanged(state="thinking"),
        StateChanged(state="speaking"),
        AudioChunk(turn_seq=1, chunk_seq=1, audio=b"pcmwav"),
        TurnCompleted(turn_seq=1, ends_call=False),
    ))
    assert result == "ok"
    assert ws.sent[0] == {"type": "state", "value": "thinking"}
    assert ws.sent[1] == {"type": "state", "value": "speaking"}
    # ADR 0033: the chunk's JSON descriptor is immediately followed by its bytes
    assert ws.sent[2] == {"type": "turn.audio.chunk", "turn_seq": 1, "chunk_seq": 1}
    assert ws.sent[3] == b"pcmwav"
    assert ws.sent[4] == {"type": "turn.completed", "turn_seq": 1}


async def test_forward_turn_events_reports_call_end():
    ws = FakeWebSocket()
    result = await session_ws._forward_turn_events(ws, _events(
        TurnCompleted(turn_seq=3, ends_call=True),
    ))
    assert result == "completed"


async def test_forward_turn_events_reports_failure():
    ws = FakeWebSocket()
    result = await session_ws._forward_turn_events(ws, _events(
        Failed(code="llm_failed", message="boom"),
    ))
    assert result == "failed"
    assert ws.sent[-1] == {"type": "error", "code": "llm_failed", "message": "boom"}


async def test_receive_json_tolerates_malformed_input():
    ws = FakeWebSocket(["not json at all"])
    assert await session_ws._receive_json(ws) is None
