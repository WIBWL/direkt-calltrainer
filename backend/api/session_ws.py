"""WebSocket API route for the live session: wire protocol <-> SessionOrchestrator."""

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.exc import SQLAlchemyError

from backend.db import repository
from backend.db.session import session_scope
from backend.personas import Persona
from backend.scenarios import Scenario
from backend.session.models import AudioChunk, Failed, StateChanged, TurnCompleted, TurnEvent
from backend.session.orchestrator import SessionOrchestrator

logger = logging.getLogger("calltrainer")

router = APIRouter()


@router.websocket("/ws/session")
async def session_ws(websocket: WebSocket) -> None:
    """One WebSocket connection per session. Control messages are JSON;
    audio is sent as a raw binary frame right after its "turn.audio.meta" message."""
    await websocket.accept()

    handshake = await _handshake(websocket)
    if handshake is None:
        return
    persona, scenario = handshake

    session_id = str(uuid.uuid4())
    orchestrator = SessionOrchestrator(persona, scenario)
    logger.info("Session %s started: persona=%s language=%s", session_id, persona.id, persona.language_id)

    await websocket.send_json({"type": "session.started", "session_id": session_id})

    try:
        # Persona opens the call
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
        # Client can disconnect between _run_session and final send
        # e.g. ASGI message 'websocket.send' after 'websocket.close'
        logger.info("Session %s: client disconnected before session.ended could be sent", session_id)
        return
    logger.info("Session %s ended (%s)", session_id, reason)


async def _handshake(websocket: WebSocket) -> tuple[Persona, Scenario] | None:
    """Reads the required `session.start` message, closing the socket and
    returning None on any malformed or unknown input."""
    try:
        start = await websocket.receive_json()
    except WebSocketDisconnect:
        return None
    if start.get("type") != "session.start":
        # Protocol Error (1002; https://websocket.org/reference/close-codes/)
        await websocket.close(code=1002, reason="Expected session.start")
        return None

    persona_id = start.get("persona_id")
    scenario_id = start.get("scenario_id")
    try:
        # Off the event loop: session_scope() is a synchronous SQLAlchemy
        # session, and this coroutine goes on to stream live audio.
        persona, scenario = await asyncio.to_thread(_load_setup, persona_id, scenario_id)
    except SQLAlchemyError as e:
        logger.error("Loading session setup failed: %s", e)
        # Internal Error (1011; https://websocket.org/reference/close-codes/)
        await websocket.close(code=1011, reason="Database unavailable")
        return None

    if persona is None or scenario is None:
        # Protocol Error (1002; https://websocket.org/reference/close-codes/)
        await websocket.close(code=1002, reason="Unknown persona_id/scenario_id")
        return None
    return persona, scenario


def _load_setup(persona_id: str | None, scenario_id: str | None) -> tuple[Persona | None, Scenario | None]:
    """Resolves the client's Persona/Scenario keys against the database."""
    with session_scope() as db:
        persona = repository.find_persona(db, persona_id) if persona_id else None
        scenario = repository.find_scenario(db, scenario_id) if scenario_id else None
    return persona, scenario


async def _run_session(websocket: WebSocket, orchestrator: SessionOrchestrator) -> str:
    """Session runs until the user ends the session, a turn fails, or the
    persona ends the call naturally ("user", "error", or "completed")."""
    while True:
        envelope = await _receive_json(websocket)
        if envelope is None or envelope.get("type") == "session.end":
            return "user"
        if envelope.get("type") != "turn.audio.meta":
            continue

        audio_bytes = await _receive_bytes(websocket)
        if audio_bytes is None:
            return "user"

        turn = orchestrator.run_turn(audio_bytes, "turn.webm", envelope.get("mime_type"))
        outcome = await _forward_turn_events(websocket, turn)
        if outcome != "ok":
            return "error" if outcome == "failed" else "completed"


async def _forward_turn_events(websocket: WebSocket, events: AsyncIterator[TurnEvent]) -> str:
    """Forwards the events of a turn. Returns "failed" if the turn failed,
    "completed" if the persona or the user ended the call naturally, else "ok"."""
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
