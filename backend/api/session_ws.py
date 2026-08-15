"""WebSocket API route for the live Session: wire protocol <-> SessionOrchestrator."""

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
    orchestrator = SessionOrchestrator(persona, scenario, language_id, language_name)
    logger.info("Session %s started: persona=%s language=%s", session_id, persona.id, language_name)

    await websocket.send_json({"type": "session.started", "session_id": session_id})

    try:
        # The Persona opens the call (a freshly generated, varied line) before
        # the client ever gets a chance to send a Turn.
        if await _forward_turn_events(websocket, orchestrator.run_opening_turn()):
            reason = "error"
        else:
            reason = await _run_session(websocket, orchestrator)
    except WebSocketDisconnect:
        logger.info("Session %s: client disconnected", session_id)
        return

    transcript = [
        {"turn_seq": t.seq, "user_text": t.user_text, "persona_text": t.persona_text}
        for t in orchestrator.turns
    ]
    await websocket.send_json({"type": "session.ended", "reason": reason, "transcript": transcript})
    await websocket.close()
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


async def _run_session(websocket: WebSocket, orchestrator: SessionOrchestrator) -> str:
    """Runs Turns until the client ends the Session or a Turn fails. Returns
    the Session's end reason ("user" or "error")."""
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
        if await _forward_turn_events(websocket, turn):
            return "error"


async def _forward_turn_events(websocket: WebSocket, events: AsyncIterator[TurnEvent]) -> bool:
    """Forwards one Turn's events over the wire. Returns True if the Turn
    failed (an ADR 0017/0026 retry was exhausted)."""
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
        elif isinstance(event, Failed):
            await websocket.send_json({"type": "error", "code": event.code, "message": event.message})
            return True
    return False


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
