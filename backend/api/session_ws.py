"""WebSocket API route for the live session: wire protocol <-> SessionOrchestrator."""

import asyncio
import contextlib
import json
import logging
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.logging_config import reset_session_log, session_id_scope
from backend.personas import PERSONAS, Persona
from backend.scenarios import SCENARIOS, Scenario
from backend.session import persistence
from backend.session.models import (
    AudioChunk,
    Failed,
    StateChanged,
    TurnCompleted,
    TurnEvent,
    utterances,
)
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
    persona, scenario = handshake

    session_id = uuid.uuid4()
    started_at = datetime.now()
    reset_session_log()
    with session_id_scope(str(session_id)):
        orchestrator = SessionOrchestrator(persona, scenario)
        logger.info("Session started: persona=%s language=%s", persona.id, persona.language_id)

        await websocket.send_json({"type": "session.started", "session_id": str(session_id)})

        try:
            # Persona opens the call
            outcome = await _run_turn_interruptible(
                websocket, orchestrator.run_opening_turn(), orchestrator.start_playback
            )
            if outcome in ("ok", "interrupted"):
                reason = await _run_session(websocket, orchestrator, orchestrator.start_playback)
            else:
                reason = "error" if outcome == "failed" else outcome
        except WebSocketDisconnect:
            logger.info("Client disconnected")
            return

        # Flattened by the same function the persisted Turn rows come from, so
        # the log the user sees cannot disagree with the one that was stored --
        # and carries the offsets that make it a timestamped Gesprächsprotokoll.
        transcript = [
            {"sprecher": u.sprecher, "text": u.text, "offset_ms": u.offset_ms}
            for u in utterances(orchestrator.turns)
        ]
        # Before session.ended, so the row exists by the time the client can
        # ask for its Feedback -- a 404 then means the write genuinely failed,
        # not that the client was merely early.
        await _record(session_id, persona, scenario, orchestrator, started_at, reason)
        try:
            await websocket.send_json({"type": "session.ended", "reason": reason, "transcript": transcript})
            await websocket.close()
        except (WebSocketDisconnect, RuntimeError):
            # Client can disconnect between _run_session and final send
            # e.g. ASGI message 'websocket.send' after 'websocket.close'
            logger.info("Client disconnected before session.ended could be sent")
            return
        logger.info("Session ended (%s)", reason)


async def _record(
    session_id: uuid.UUID,
    persona: Persona,
    scenario: Scenario,
    orchestrator: SessionOrchestrator,
    started_at: datetime,
    reason: str,
) -> None:
    """Persist the finished Session and queue its wrap-up (ADR 0034, ADR 0019).

    Dispatched off the event loop because the ORM is synchronous, and never
    allowed to raise: the call is already over, and neither a database nor a
    Redis outage may cost the user the transcript they are waiting for.
    """
    try:
        db_id = await asyncio.to_thread(
            persistence.persist_session,
            session_id, persona, scenario, orchestrator.turns, started_at, reason,
        )
    except Exception:
        logger.exception("Session could not be persisted; it is lost")
        return
    try:
        # Imported here, not at module scope: the live path must not need
        # Redis to be importable, let alone reachable.
        from backend.feedback import queue

        await asyncio.to_thread(queue.enqueue_feedback, db_id)
    except Exception:
        logger.exception("Feedback could not be queued for session %d", db_id)


async def _handshake(websocket: WebSocket) -> tuple[Persona, Scenario] | None:
    """Reads the required `session.start` message, closing the socket and
    returning None on any malformed or unknown input."""
    try:
        start = await websocket.receive_json()
    except WebSocketDisconnect:
        return None
    if start.get("type") != "session.start":
        logger.warning("Handshake failed: expected session.start, got %r", start.get("type"))
        # Protocol Error (1002; https://websocket.org/reference/close-codes/)
        await websocket.close(code=1002, reason="Expected session.start")
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
    return persona, scenario


async def _run_session(
    websocket: WebSocket, orchestrator: SessionOrchestrator, on_activate: Callable[[], None]
) -> str:
    """Session runs until the user ends the session, a turn fails, or the
    persona ends the call naturally ("user", "error", or "completed").

    Takes `on_activate` for the same reason _wait_for_control_message does:
    session.activate lands in whichever receive loop happens to own the socket
    at that moment. The opening turn is usually already forwarded by the time
    the user leaves the mic check, so that is normally this loop, not that one.
    """
    while True:
        envelope = await _receive_json(websocket)
        if envelope is None or envelope.get("type") == "session.end":
            return "user"
        if envelope.get("type") == "session.activate":
            on_activate()
            continue
        if envelope.get("type") == "turn.interrupt":
            continue
        if envelope.get("type") != "turn.audio.meta":
            continue

        audio_bytes = await _receive_bytes(websocket)
        if audio_bytes is None:
            return "user"

        turn = orchestrator.run_turn(audio_bytes, "turn.webm", envelope.get("mime_type"))
        outcome = await _run_turn_interruptible(websocket, turn, orchestrator.start_playback)
        if outcome == "interrupted":
            continue
        if outcome != "ok":
            return "error" if outcome == "failed" else outcome


async def _run_turn_interruptible(
    websocket: WebSocket, events: AsyncIterator[TurnEvent], on_activate: Callable[[], None]
) -> str:
    """Forwards one turn's events while racing session.end/disconnect/a user
    barge-in, so talking over the persona doesn't wait for it to finish."""
    forward_task = asyncio.create_task(_forward_turn_events(websocket, events))
    control_task = asyncio.create_task(_wait_for_control_message(websocket, on_activate))
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


async def _wait_for_control_message(
    websocket: WebSocket, on_activate: Callable[[], None]
) -> str:
    """Waits for a client message that should interrupt the in-flight turn:
    session.end/disconnect ends the session, turn.interrupt is a barge-in.

    session.activate is neither -- it usually arrives *during* the opening
    turn, which is exactly the point (ADR 0048) -- so it starts the clock and
    the wait continues.
    """
    while True:
        envelope = await _receive_json(websocket)
        if envelope is None or envelope.get("type") == "session.end":
            return "end"
        if envelope.get("type") == "turn.interrupt":
            return "interrupt"
        if envelope.get("type") == "session.activate":
            on_activate()


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
