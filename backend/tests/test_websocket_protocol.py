"""The /ws/session protocol through a fake WebSocket (F-46, F-50, ADR 0009, 0033, 0035, 0109, 0110)."""

import asyncio
import json
from dataclasses import replace

import pytest
from fastapi import WebSocketDisconnect

from shared.db import models as db_models
from backend import auth, limits
from backend.api import session_ws
from backend.session import persistence
from backend.session.events import AudioChunk, Failed, StateChanged, TurnCompleted
from backend.session.orchestrator import SessionOrchestrator
from backend.tests.conftest import TEST_AUTH, TEST_PERSONAS, TEST_SCENARIOS

# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access
# pylint: disable=unused-argument  # driving session_ws's private helpers is the point


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


def _far_deadline() -> float:
    """A call deadline no test here reaches."""
    return asyncio.get_running_loop().time() + 3600


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


class _FakeOrchestrator:
    """Just the hooks _run_session calls, plus a one-event `run_turn` whose
    reply ends the call (for the revive test below)."""

    def __init__(self):
        self.late_barge_ins = []
        self.barge_ins = []
        self.activated = 0
        self.ended = False
        self.turns_run = 0

    def start_playback(self):
        self.activated += 1

    def pickup_prompt_delay(self):
        return None

    def note_late_barge_in(self, played_ms):
        self.late_barge_ins.append(played_ms)

    def note_barge_in(self, played_ms):
        self.barge_ins.append(played_ms)

    async def run_turn(self, _audio, _filename, _content_type):
        self.turns_run += 1
        yield StateChanged(state="speaking")
        yield AudioChunk(turn_seq=self.turns_run, chunk_seq=1, audio=b"goodbye")
        self.ended = True  # this reply ended the call
        yield TurnCompleted(turn_seq=self.turns_run, ends_call=True)


async def test_run_session_routes_a_between_turns_interrupt_to_the_orchestrator():
    ws = FakeWebSocket([
        {"type": "turn.interrupt", "played_ms": 1500},
        {"type": "session.end"},
    ])
    orch = _FakeOrchestrator()

    reason = await session_ws._run_session(ws, orch, orch.start_playback, deadline=_far_deadline())

    assert reason == "user"
    assert orch.late_barge_ins == [1500]


async def test_a_barge_in_over_the_goodbye_ends_the_session_instead_of_reviving_it():
    ws = FakeWebSocket([
        {"type": "turn.audio.meta", "turn_seq": 1, "mime_type": "audio/wav"},
        b"user-audio",
        {"type": "turn.interrupt", "played_ms": 400},   # over the goodbye's tail
        {"type": "turn.audio.meta", "turn_seq": 2, "mime_type": "audio/wav"},  # must never be consumed
        b"more-audio",
    ])
    orch = _FakeOrchestrator()

    reason = await session_ws._run_session(ws, orch, orch.start_playback, deadline=_far_deadline())

    assert reason == "completed"
    assert orch.turns_run == 1, "no further Turn on a finished call"


async def test_a_disconnect_mid_call_is_not_read_as_the_user_ending_it():
    ws = FakeWebSocket([_DISCONNECT])
    with pytest.raises(WebSocketDisconnect):
        await session_ws._receive_json(ws)


async def test_a_malformed_control_message_is_still_not_a_disconnect():
    ws = FakeWebSocket(["{not json at all"])
    assert await session_ws._receive_json(ws) is None


def test_a_disconnected_session_is_stored_as_aborted():
    assert persistence._STATUS["disconnected"] == db_models.STATUS_ABORTED
    assert persistence._STATUS["user"] == db_models.STATUS_COMPLETED


class FrameWebSocket:
    """Lets a binary frame arrive where text is expected."""

    def __init__(self, frame):
        self.frame = frame
        self.closed = None

    async def receive_text(self):
        return self.frame["text"]

    async def receive_bytes(self):
        return self.frame["bytes"]

    async def receive_json(self):
        return json.loads(self.frame["text"])

    async def close(self, code=1000, reason=""):
        self.closed = (code, reason)


@pytest.mark.parametrize(
    "frame",
    [{"text": "42"}, {"text": "[1, 2]"}, {"text": "\"a string\""},
     {"text": "{not json"}, {"bytes": b"\x00\x01"}],
    ids=["scalar", "array", "string", "unparseable", "binary-frame"],
)
async def test_only_a_json_object_counts_as_a_control_message(frame):
    assert await session_ws._receive_json(FrameWebSocket(frame)) is None


async def test_a_text_frame_where_the_audio_blob_belongs_is_not_a_crash():
    assert await session_ws._receive_bytes(FrameWebSocket({"text": "oops"})) is None


async def test_a_handshake_that_is_not_json_closes_the_socket(fake_library):  # noqa: ARG001
    ws = FrameWebSocket({"bytes": b"\x00"})
    assert await session_ws._handshake(ws) is None
    assert ws.closed[0] == 1002


async def test_a_disconnect_during_a_turn_still_tears_the_turn_down():
    closed = asyncio.Event()
    forwarded = []

    async def events():
        try:
            for i in range(10_000):
                await asyncio.sleep(0)
                yield AudioChunk(turn_seq=1, chunk_seq=i, audio=b"pcm")
        finally:
            closed.set()

    class Dropping(FakeWebSocket):
        async def receive_text(self):
            await asyncio.sleep(0.01)  # let the forwarder get going first
            raise WebSocketDisconnect(code=1006)

        async def send_json(self, data):
            forwarded.append(data)

        async def send_bytes(self, data):
            forwarded.append(data)

    turn = events()
    with pytest.raises(WebSocketDisconnect):
        await session_ws._run_turn_interruptible(
            Dropping(), turn, lambda: None, lambda _ms: None
        )

    assert closed.is_set(), "the turn generator was closed"
    sent_by_then = len(forwarded)
    await asyncio.sleep(0.05)
    assert len(forwarded) == sent_by_then, "and nothing kept forwarding behind it"


async def test_a_forwarder_that_already_failed_still_closes_the_turn():
    closed = asyncio.Event()

    async def events():
        try:
            while True:
                await asyncio.sleep(0)
                yield AudioChunk(turn_seq=1, chunk_seq=1, audio=b"pcm")
        finally:
            closed.set()

    async def already_failed():
        raise RuntimeError("Unexpected ASGI message 'websocket.send'")

    forwarder = asyncio.create_task(already_failed())
    await asyncio.sleep(0)
    turn = events()
    await turn.__anext__()  # park it at a yield, as a live turn would be

    with pytest.raises(RuntimeError):
        await session_ws._tear_down_turn(forwarder, turn)

    assert closed.is_set(), "the turn generator was closed all the same"


class SilentWebSocket(FakeWebSocket):
    """A client that opens the socket and never says anything."""

    async def receive_json(self):
        await asyncio.Event().wait()

    async def receive_text(self):
        await asyncio.Event().wait()


def _error_codes(ws: FakeWebSocket) -> list[str]:
    return [m["code"] for m in ws.sent if isinstance(m, dict) and m.get("type") == "error"]


async def test_a_socket_that_never_sends_session_start_is_closed(monkeypatch):
    monkeypatch.setattr(session_ws, "HANDSHAKE_TIMEOUT_S", 0.05)
    ws = SilentWebSocket()
    assert await session_ws._handshake(ws) is None
    assert ws.closed[0] == 1008


async def test_a_caller_without_the_role_is_refused_and_told_why(monkeypatch, fake_library):
    outsider = auth.AuthContext(sub="outsider", roles=[], token="t")
    monkeypatch.setattr(session_ws, "authenticate_ws", lambda msg: outsider)
    ws = FakeWebSocket([_START])
    assert await session_ws._handshake(ws) is None
    assert ws.closed[0] == 1008
    assert _error_codes(ws) == ["not_admitted"]


async def test_a_call_over_the_open_call_cap_is_refused(monkeypatch, fake_library):
    monkeypatch.setattr(limits, "OPEN_CALLS", limits.CallSlots(0))
    served = []

    async def serve(*_args):
        served.append(True)

    monkeypatch.setattr(session_ws, "_serve_call", serve)
    ws = FakeWebSocket([_START])
    await session_ws.session_ws(ws)
    assert not served, "no Persona spoke on a refused call"
    assert ws.closed[0] == 1008
    assert _error_codes(ws) == ["too_many_calls"]


async def test_a_call_gives_its_slot_back_however_it_ends(monkeypatch, fake_library):
    monkeypatch.setattr(limits, "OPEN_CALLS", limits.CallSlots(1))
    served = []

    async def serve(*_args):
        served.append(True)
        raise RuntimeError("the call fell over")

    monkeypatch.setattr(session_ws, "_serve_call", serve)
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await session_ws.session_ws(FakeWebSocket([_START]))
    assert len(served) == 2


async def test_a_call_past_its_time_limit_ends_between_turns():
    ws = SilentWebSocket()
    orch = _FakeOrchestrator()
    deadline = asyncio.get_running_loop().time() + 0.05

    reason = await session_ws._run_session(ws, orch, orch.start_playback, deadline=deadline)

    assert reason == "completed"
    assert _error_codes(ws) == ["time_limit"]
    assert orch.turns_run == 0


async def test_an_oversized_turn_never_reaches_the_pipeline(monkeypatch):
    monkeypatch.setattr(session_ws, "MAX_TURN_AUDIO_BYTES", 10)
    ws = FakeWebSocket([
        {"type": "turn.audio.meta", "turn_seq": 1, "mime_type": "audio/wav"},
        b"x" * 11,
        {"type": "session.end"},
    ])
    orch = _FakeOrchestrator()

    reason = await session_ws._run_session(ws, orch, orch.start_playback, deadline=_far_deadline())

    assert reason == "user"
    assert orch.turns_run == 0
    assert {"type": "state", "value": "listening"} in ws.sent


async def test_an_ordinary_call_waits_for_the_user_to_pick_up(persona, scenario, fake_pipeline):
    ws = FakeWebSocket()
    orch = SessionOrchestrator(persona, scenario)

    outcome = await session_ws._open_call(ws, orch, scenario)

    assert outcome == "ok"
    assert ws.sent == [{"type": "state", "value": "listening"}]
    assert not fake_pipeline.llm.calls
    assert not orch.turns


class _QuietWebSocket(FakeWebSocket):
    """A client that says nothing while the opening Turn runs, rather than
    one that has already gone away."""

    async def receive_text(self):
        await asyncio.Event().wait()


async def test_a_reverse_call_is_answered_by_the_persona(persona, scenario, fake_pipeline):
    reverse = replace(scenario, reverse=True)
    fake_pipeline.llm.replies = ["Kundenservice, Brandt, was kann ich für Sie tun?"]
    ws = _QuietWebSocket()
    orch = SessionOrchestrator(persona, reverse)

    outcome = await session_ws._open_call(ws, orch, reverse)

    assert outcome == "ok"
    assert any(isinstance(m, bytes) for m in ws.sent), "the answering line is spoken"
    assert orch.turns[0].persona_text == "Kundenservice, Brandt, was kann ich für Sie tun?"
    assert orch.turns[0].user_text == ""


class _PromptingOrchestrator(_FakeOrchestrator):
    """Due to ask "Hallo?" once, straight away; nothing after that."""

    def __init__(self):
        super().__init__()
        self.prompts_run = 0
        self.speaking = 0

    def pickup_prompt_delay(self):
        return 0.01 if self.prompts_run == 0 else None

    def note_user_speaking(self):
        self.speaking += 1

    async def run_pickup_prompt(self):
        self.prompts_run += 1
        yield StateChanged(state="speaking")
        yield AudioChunk(turn_seq=1, chunk_seq=1, audio=b"hallo")
        yield TurnCompleted(turn_seq=1, ends_call=False)
        yield StateChanged(state="listening")


class _SilentFirst(FakeWebSocket):
    """Says nothing at first -- the receive is cancelled by the silence timer --
    and then plays out its messages."""

    def __init__(self, incoming):
        super().__init__(incoming)
        self._silent = True

    async def receive_text(self):
        if self._silent:
            self._silent = False
            await asyncio.Event().wait()
        return await super().receive_text()


async def test_a_silent_line_gets_a_prompt_and_the_call_goes_on():
    ws = _SilentFirst([{"type": "session.end"}])
    orch = _PromptingOrchestrator()

    reason = await session_ws._run_session(ws, orch, orch.start_playback, deadline=_far_deadline())

    assert reason == "user"
    assert orch.prompts_run == 1
    assert b"hallo" in ws.sent
    assert {"type": "state", "value": "listening"} in ws.sent


async def test_the_client_reporting_speech_reaches_the_orchestrator():
    ws = FakeWebSocket([{"type": "user.speaking"}, {"type": "session.end"}])
    orch = _PromptingOrchestrator()
    orch.prompts_run = 1  # nothing due, so the report is all that happens

    reason = await session_ws._run_session(ws, orch, orch.start_playback, deadline=_far_deadline())

    assert reason == "user"
    assert orch.speaking == 1
