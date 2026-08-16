"""WebSocket API route for the live Session: wire protocol <-> SessionOrchestrator."""

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.languages import LANGUAGES
from backend.personas import PERSONAS, Persona
from backend.scenarios import DEFAULT_SCENARIO_ID, SCENARIOS, Scenario
from backend.session.models import AudioChunk, Failed, StateChanged, TurnCompleted, TurnEvent
from backend.session.orchestrator import SessionOrchestrator

logger = logging.getLogger("calltrainer")

router = APIRouter()


@router.websocket("/ws/session")
async def session_ws(websocket: WebSocket) -> None:
    """One WebSocket connection per Session. Wire protocol: JSON control
    messages; binary audio sent as a raw WS binary frame immediately following
    its JSON "meta" message — WS delivery order on one connection is
    guaranteed, so client and server pair them positionally (see ADR 0026)."""
    await websocket.accept()

    handshake = await _handshake(websocket)
    if handshake is None:
        return
    persona, language_id, language_name, scenario = handshake

    session_id = str(uuid.uuid4())
    orchestrator = SessionOrchestrator(persona, scenario, language_id)
    logger.info("Session %s started: persona=%s language=%s", session_id, persona.id, language_name)

    await websocket.send_json({"type": "session.started", "session_id": session_id})

    try:
        # The Persona opens the call (a freshly generated, varied line) before
        # the client ever gets a chance to send a Turn.
        outcome = await _forward_turn_events(websocket, orchestrator.run_opening_turn())
        if outcome == "failed":
            reason = "error"
        elif outcome == "completed":
            reason = "completed"
        else:
            reason = await _run_session(websocket, orchestrator)
    except WebSocketDisconnect:
        logger.info("Session %s: client disconnected", session_id)
        return

    transcript = [
        {"turn_seq": t.seq, "user_text": t.user_text, "persona_text": t.persona_text}
        for t in orchestrator.turns
    ]
    try:
        await websocket.send_json({"type": "session.ended", "reason": reason, "transcript": transcript})
        await websocket.close()
    except (WebSocketDisconnect, RuntimeError):
        # The client can disconnect in the narrow window between _run_session
        # returning and this final send — observed in testing as uvicorn's
        # ASGI layer raising a plain RuntimeError ("Unexpected ASGI message
        # 'websocket.send', after sending 'websocket.close'"), not the
        # higher-level WebSocketDisconnect the rest of this module catches.
        # Nothing to recover: the client is already gone.
        logger.info("Session %s: client disconnected before session.ended could be sent", session_id)
        return
    logger.info("Session %s ended (%s)", session_id, reason)


async def _handshake(websocket: WebSocket) -> tuple[Persona, str, str, Scenario] | None:
    """Reads the required `session.start` message, closing the socket and
    returning None on any malformed or unknown input."""
    try:
        start = await websocket.receive_json()
    except WebSocketDisconnect:
        return None
    if start.get("type") != "session.start":
        await websocket.close(code=1002, reason="Expected session.start")
        return None

    persona = PERSONAS.get(start.get("persona_id"))
    language_id = start.get("language_id")
    language_name = LANGUAGES.get(language_id)
    scenario = SCENARIOS.get(start.get("scenario_id") or DEFAULT_SCENARIO_ID)
    if persona is None or language_name is None or scenario is None:
        await websocket.close(code=1002, reason="Unknown persona_id/language_id/scenario_id")
        return None
    return persona, language_id, language_name, scenario


class _SessionDone(Exception):
    """Internal control-flow signal: the Session loop should stop, with the
    given end reason ("user" here — "error"/"completed" instead return
    directly from the loop once the in-flight Turn Task settles)."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


async def _run_session(websocket: WebSocket, orchestrator: SessionOrchestrator) -> str:
    """Runs Turns until the client ends the Session, a Turn fails, or the
    Persona ends the call naturally. Returns the Session's end reason
    ("user", "error", or "completed").

    One Turn's events are forwarded from a background Task (`turn_task`)
    rather than awaited inline, so this loop can keep reading incoming
    messages while a reply is still being generated/spoken — required for
    barge-in: a "turn.interrupt" (sent the instant the client's VAD hears the
    user start talking, see ADR 0026's follow-up) or a fresh
    "turn.audio.meta" arriving mid-reply cancels that Task, via
    `_handle_envelope`. Cancelling mid-`websocket.send`, though possible in
    principle, isn't specially guarded against here — the resulting
    exception would just end the Session via the normal
    WebSocketDisconnect/exception handling in `session_ws`, not corrupt
    Session state, so it's an accepted simplification rather than adding a
    send-shielding mechanism for what should be a rare race.

    Exactly one `_receive_json` call is ever outstanding at a time: Starlette
    (via the `websockets` library) allows only one reader on a WebSocket at
    once, so `receive_task` is only replaced *after* its result — and any
    `_receive_bytes` call `_handle_envelope` made off the back of it — has
    fully been consumed, never speculatively ahead of that."""
    turn_task: asyncio.Task[str] | None = None
    receive_task = asyncio.create_task(_receive_json(websocket))
    try:
        while True:
            waiting = {receive_task} | ({turn_task} if turn_task is not None else set())
            done, _ = await asyncio.wait(waiting, return_when=asyncio.FIRST_COMPLETED)

            if turn_task is not None and turn_task in done:
                outcome = turn_task.result()
                turn_task = None
                if outcome != "ok":
                    receive_task.cancel()
                    return "error" if outcome == "failed" else "completed"

            if receive_task not in done:
                continue
            envelope = receive_task.result()
            turn_task = await _handle_envelope(websocket, orchestrator, envelope, turn_task)
            receive_task = asyncio.create_task(_receive_json(websocket))
    except _SessionDone as done:
        return done.reason
    finally:
        receive_task.cancel()
        if turn_task is not None:
            turn_task.cancel()


async def _handle_envelope(
    websocket: WebSocket,
    orchestrator: SessionOrchestrator,
    envelope: dict | None,
    turn_task: asyncio.Task[str] | None,
) -> asyncio.Task[str] | None:
    """Reacts to one incoming control message, returning the (possibly new,
    possibly unchanged) in-flight Turn Task. Raises `_SessionDone` if the
    Session should end right here (client hung up or ended it)."""
    if envelope is None or envelope.get("type") == "session.end":
        if turn_task is not None:
            turn_task.cancel()
        raise _SessionDone("user")

    if envelope.get("type") == "turn.interrupt":
        if turn_task is not None:
            turn_task.cancel()
            await websocket.send_json({"type": "state", "value": "listening"})
        return None

    if envelope.get("type") != "turn.audio.meta":
        return turn_task

    audio_bytes = await _receive_bytes(websocket)
    if audio_bytes is None:
        if turn_task is not None:
            turn_task.cancel()
        raise _SessionDone("user")

    if turn_task is not None:
        turn_task.cancel()
    turn = orchestrator.run_turn(audio_bytes, "turn.webm", envelope.get("mime_type"))
    return asyncio.create_task(_forward_turn_events(websocket, turn))


async def _forward_turn_events(websocket: WebSocket, events: AsyncIterator[TurnEvent]) -> str:
    """Forwards one Turn's events over the wire. Returns "failed" if the Turn
    failed (an ADR 0017/0026 retry was exhausted), "completed" if the Persona
    (or the user, via a farewell) ended the call naturally, else "ok"."""
    async for event in events:
        if isinstance(event, StateChanged):
            await websocket.send_json({"type": "state", "value": event.state})
        elif isinstance(event, AudioChunk):
            await websocket.send_json(
                {"type": "turn.audio.chunk", "turn_seq": event.turn_seq, "chunk_seq": event.chunk_seq}
            )
            await websocket.send_bytes(event.audio)
        elif isinstance(event, TurnCompleted):
            await websocket.send_json({"type": "turn.completed", "turn_seq": event.turn_seq})
            if event.ends_call:
                return "completed"
        elif isinstance(event, Failed):
            await websocket.send_json({"type": "error", "code": event.code, "message": event.message})
            return "failed"
    return "ok"


async def _receive_json(websocket: WebSocket) -> dict | None:
    """Receives one JSON control message, or None on disconnect/malformed input."""
    try:
        raw = await websocket.receive_text()
    except WebSocketDisconnect:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


async def _receive_bytes(websocket: WebSocket) -> bytes | None:
    """Receives one binary audio frame, or None on disconnect/malformed input."""
    try:
        return await websocket.receive_bytes()
    except WebSocketDisconnect:
        return None
