"""The `/ws/session` route: wire protocol on one side, `SessionOrchestrator` on
the other.

A WebSocket, not REST, because the live call streams audio both ways and the
user can talk over the persona (ADR 0033, ADR 0035). The token rides in the
first message — a browser cannot header a WebSocket (ADR 0009).
"""

import asyncio
import contextlib
import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Literal

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.auth import AuthContext, authenticate_ws
from backend.logging_config import reset_session_log, session_id_scope
from backend.personas import PERSONAS, Persona
from backend.scenarios import SCENARIOS, Scenario
from backend.session.models import AudioChunk, Failed, StateChanged, TurnCompleted, TurnEvent
from backend.session.orchestrator import SessionOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/session")
async def session_ws(websocket: WebSocket) -> None:
    """One WebSocket connection per session. Control messages are JSON;
    audio is sent as a raw binary frame right after its "turn.audio.meta" message."""
    await websocket.accept()

    handshake = await _handshake(websocket)
    if handshake is None:
        return
    persona, scenario, auth = handshake

    session_id = str(uuid.uuid4())
    reset_session_log()
    with session_id_scope(session_id):
        orchestrator = SessionOrchestrator(persona, scenario, subject_id=auth.sub)
        logger.info(
            "Session started: subject=%s persona=%s language=%s", auth.sub, persona.id, persona.language_id
        )

        await websocket.send_json({"type": "session.started", "session_id": session_id})

        try:
            # The persona speaks first (F-01): the opening Turn has no user
            # utterance, but is otherwise a normal interruptible Turn.
            outcome = await _run_turn_interruptible(websocket, orchestrator.run_opening_turn())
            if outcome in ("ok", "interrupted"):
                reason = await _run_session(websocket, orchestrator)
            else:
                # The opening Turn itself ended the Session: "failed" is the Turn
                # vocabulary for what the client is told as "error"; "completed"
                # and "user" carry over unchanged.
                reason = "error" if outcome == "failed" else outcome
        except WebSocketDisconnect:
            logger.info("Client disconnected")
            return

        transcript = [
            {"turn_seq": t.seq, "user_text": t.user_text, "persona_text": t.persona_text}
            for t in orchestrator.turns
        ]
        try:
            await websocket.send_json({"type": "session.ended", "reason": reason, "transcript": transcript})
            await websocket.close()
        except (WebSocketDisconnect, RuntimeError):
            # The client can drop before this final send; Starlette then raises
            # RuntimeError ("send after close"), not WebSocketDisconnect. The
            # transcript is lost with the connection — the accepted trade in
            # ADR 0034 (a mid-call disconnect leaves no record).
            logger.info("Client disconnected before session.ended could be sent")
            return
        logger.info("Session ended (%s)", reason)


async def _handshake(websocket: WebSocket) -> tuple[Persona, Scenario, AuthContext] | None:
    """Reads the required `session.start` message, closing the socket and
    returning None on any malformed, unauthenticated or unknown input."""
    try:
        start = await websocket.receive_json()
    except WebSocketDisconnect:
        return None
    if start.get("type") != "session.start":
        logger.warning("Handshake failed: expected session.start, got %r", start.get("type"))
        # Protocol Error (1002; https://websocket.org/reference/close-codes/)
        await websocket.close(code=1002, reason="Expected session.start")
        return None

    # A browser can't set an Authorization header on a WebSocket, so the token
    # rides in the handshake message (ADR 0009).
    auth = authenticate_ws(start)
    if auth is None:
        logger.warning("Handshake failed: missing or invalid token")
        # Policy Violation (1008; https://websocket.org/reference/close-codes/)
        await websocket.close(code=1008, reason="Authentication required")
        return None

    persona_id = start.get("persona_id")
    scenario_id = start.get("scenario_id")
    persona = next((p for p in PERSONAS if p.id == persona_id), None)
    scenario = next((s for s in SCENARIOS if s.id == scenario_id), None)
    if persona is None or scenario is None:
        logger.warning("Handshake failed: unknown persona_id=%r/scenario_id=%r", persona_id, scenario_id)
        # Protocol Error (1002; https://websocket.org/reference/close-codes/)
        await websocket.close(code=1002, reason="Unknown persona_id/scenario_id")
        return None
    return persona, scenario, auth


# The three vocabularies threaded through the turn/session helpers, spelled out
# so a typo in a return or comparison is a type error rather than a silent
# fall-through:
_TurnResult = Literal["ok", "failed", "completed"]           # what _forward_turn_events reports
_ControlMessage = Literal["end", "interrupt"]                 # what pre-empted an in-flight turn
_TurnOutcome = Literal["ok", "failed", "completed", "interrupted", "user"]  # after the control race
_SessionEndReason = Literal["user", "error", "completed"]     # sent to the client in session.ended


async def _run_session(websocket: WebSocket, orchestrator: SessionOrchestrator) -> _SessionEndReason:
    """Session runs until the user ends the session, a turn fails, or the
    persona ends the call naturally ("user", "error", or "completed")."""
    while True:
        envelope = await _receive_json(websocket)
        if envelope is None or envelope.get("type") == "session.end":
            return "user"
        # Between Turns nothing is playing, so a stray `turn.interrupt` — or any
        # unrecognised message — is skipped, not an error (client and server
        # versions need not match exactly).
        if envelope.get("type") != "turn.audio.meta":
            continue

        audio_bytes = await _receive_bytes(websocket)
        if audio_bytes is None:
            return "user"

        turn = orchestrator.run_turn(audio_bytes, "turn.webm", envelope.get("mime_type"))
        outcome = await _run_turn_interruptible(websocket, turn)
        if outcome == "interrupted":
            continue
        if outcome != "ok":
            return "error" if outcome == "failed" else outcome


async def _run_turn_interruptible(
    websocket: WebSocket, events: AsyncIterator[TurnEvent]
) -> _TurnOutcome:
    """Forwards one turn's events while racing session.end/disconnect/a user
    barge-in, so talking over the persona doesn't wait for it to finish."""
    forward_task = asyncio.create_task(_forward_turn_events(websocket, events))
    control_task = asyncio.create_task(_wait_for_control_message(websocket))
    done, _ = await asyncio.wait({forward_task, control_task}, return_when=asyncio.FIRST_COMPLETED)

    if control_task in done:
        forward_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await forward_task
        # Cancelling forward_task doesn't reliably tear down the turn
        # generator itself (see SessionOrchestrator._generate_reply); this does.
        await events.aclose()
        if control_task.result() == "interrupt":
            logger.info("User barged in")
            await websocket.send_json({"type": "state", "value": "listening"})
            return "interrupted"
        return "user"

    control_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await control_task
    return forward_task.result()


async def _wait_for_control_message(websocket: WebSocket) -> _ControlMessage:
    """Waits for a client message that should interrupt the in-flight turn:
    session.end/disconnect ends the session, turn.interrupt is a barge-in."""
    while True:
        envelope = await _receive_json(websocket)
        if envelope is None or envelope.get("type") == "session.end":
            return "end"
        if envelope.get("type") == "turn.interrupt":
            return "interrupt"


async def _forward_turn_events(
    websocket: WebSocket, events: AsyncIterator[TurnEvent]
) -> _TurnResult:
    """Translate one Turn's `TurnEvent`s to wire messages — the only place that
    mapping lives (see session/models.py). Returns "failed" on a failed leg,
    "completed" if the call ended naturally, else "ok"."""
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
