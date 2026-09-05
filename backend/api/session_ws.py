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
from collections.abc import AsyncIterator, Callable
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.exc import SQLAlchemyError

from backend.auth import AuthContext, authenticate_ws
from backend.logging_config import session_id_scope
from backend.tenants import resolve_tenant_id
from backend import library
from backend.personas import Persona
from backend.scenarios import Scenario
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
    persona, scenario, auth = handshake

    session_id = uuid.uuid4()
    started_at = datetime.now()
    # The log file keeps every Session for the process's lifetime (ADR 0055);
    # session_id_scope is what tags this call's lines so they stay separable.
    with session_id_scope(str(session_id)):
        orchestrator = SessionOrchestrator(persona, scenario)
        logger.info(
            "Session started: subject=%s persona=%s language=%s", auth.sub, persona.id, persona.language_id
        )

        await websocket.send_json({"type": "session.started", "session_id": str(session_id)})

        try:
            # The persona speaks first (F-01): the opening Turn has no user
            # utterance, but is otherwise a normal interruptible Turn.
            outcome = await _run_turn_interruptible(
                websocket,
                orchestrator.run_opening_turn(),
                orchestrator.start_playback,
                orchestrator.note_barge_in,
            )
            if outcome in ("ok", "interrupted"):
                reason = await _run_session(websocket, orchestrator, orchestrator.start_playback)
            else:
                # The opening Turn itself ended the Session: "failed" is the Turn
                # vocabulary for what the client is told as "error"; "completed"
                # and "user" carry over unchanged.
                reason = "error" if outcome == "failed" else outcome
        except WebSocketDisconnect:
            logger.info("Client disconnected")
            return

        # Flattened by the same function the persisted Turn rows come from, so
        # the log the user sees cannot disagree with the one that was stored --
        # and carries the offsets that make it a timestamped transcript.
        transcript = [
            {"speaker": u.speaker, "text": u.text, "offset_ms": u.offset_ms}
            for u in utterances(orchestrator.turns)
        ]
        # Before session.ended, so the row exists by the time the client can
        # ask for its Feedback -- a 404 then means the write genuinely failed,
        # not that the client was merely early.
        await _record(session_id, auth.sub, persona, scenario, orchestrator, started_at, reason)
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


async def _record(
    session_id: uuid.UUID,
    subject_id: str,
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
            session_id, subject_id, persona, scenario, orchestrator.turns, started_at, reason,
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


def _load_selection(
    persona_id: str | None, scenario_id: str | None, auth: AuthContext
) -> tuple[Persona | None, Scenario | None]:
    """The Persona and Scenario the handshake names, read together in one worker
    thread -- `session_scope()` is synchronous and nothing blocking may run on
    the event loop that streams live audio (CLAUDE.md, ADR 0034).

    The Scenario is scoped to the caller and their company (ADR 0060): a
    built-in, one shared with their tenant, or one of their own -- never another
    User's private Scenario. Personas are all built-ins, so they are not scoped.
    """
    persona = library.get_persona(persona_id)
    scenario = library.get_scenario(scenario_id, auth.sub, resolve_tenant_id(auth))
    return persona, scenario


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
    try:
        persona, scenario = await asyncio.to_thread(
            _load_selection, persona_id, scenario_id, auth
        )
    except SQLAlchemyError as e:
        # Not the client's fault, so not a protocol error (1002): the
        # library is unreachable. ADR 0041 puts the database on the
        # Session's start path, so this is a server-side failure.
        logger.error("Handshake failed: could not read the library: %s", e)
        await websocket.close(code=1011, reason="Persona/scenario library unavailable")
        return None
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
# A barge-in also carries how many ms of the reply the client actually played
# (None from a client too old to report it); everything else pairs with None.
_Control = tuple[_ControlMessage, int | None]
_TurnOutcome = Literal["ok", "failed", "completed", "interrupted", "user"]  # after the control race
_SessionEndReason = Literal["user", "error", "completed"]     # sent to the client in session.ended


async def _run_session(
    websocket: WebSocket, orchestrator: SessionOrchestrator, on_activate: Callable[[], None]
) -> _SessionEndReason:
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
        # Between Turns nothing is playing, so a stray `turn.interrupt` — or any
        # unrecognised message — is skipped, not an error (client and server
        # versions need not match exactly).
        if envelope.get("type") != "turn.audio.meta":
            continue

        audio_bytes = await _receive_bytes(websocket)
        if audio_bytes is None:
            return "user"

        turn = orchestrator.run_turn(audio_bytes, "turn.webm", envelope.get("mime_type"))
        outcome = await _run_turn_interruptible(
            websocket, turn, orchestrator.start_playback, orchestrator.note_barge_in
        )
        if outcome == "interrupted":
            continue
        if outcome != "ok":
            return "error" if outcome == "failed" else outcome


async def _run_turn_interruptible(
    websocket: WebSocket,
    events: AsyncIterator[TurnEvent],
    on_activate: Callable[[], None],
    on_barge_in: Callable[[int | None], None],
) -> _TurnOutcome:
    """Forwards one turn's events while racing session.end/disconnect/a user
    barge-in, so talking over the persona doesn't wait for it to finish."""
    forward_task = asyncio.create_task(_forward_turn_events(websocket, events))
    control_task = asyncio.create_task(_wait_for_control_message(websocket, on_activate))
    done, _ = await asyncio.wait({forward_task, control_task}, return_when=asyncio.FIRST_COMPLETED)

    if control_task in done:
        forward_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await forward_task
        kind, played_ms = control_task.result()
        # Hand the played-through position to the orchestrator *before* the
        # teardown below, since that is what triggers the turn's finalization.
        if kind == "interrupt":
            on_barge_in(played_ms)
        # Cancelling forward_task doesn't reliably tear down the turn
        # generator itself (see SessionOrchestrator._generate_reply); this does.
        await events.aclose()
        if kind == "interrupt":
            logger.info("User barged in (played %s ms of the reply)", played_ms)
            await websocket.send_json({"type": "state", "value": "listening"})
            return "interrupted"
        return "user"

    control_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await control_task
    return forward_task.result()


async def _wait_for_control_message(
    websocket: WebSocket, on_activate: Callable[[], None]
) -> _Control:
    """Waits for a client message that should interrupt the in-flight turn:
    session.end/disconnect ends the session, turn.interrupt is a barge-in
    (carrying how many ms of the reply the client played, ADR 0035).

    session.activate is neither -- it usually arrives *during* the opening
    turn, which is exactly the point (ADR 0051) -- so it starts the clock and
    the wait continues.
    """
    while True:
        envelope = await _receive_json(websocket)
        if envelope is None or envelope.get("type") == "session.end":
            return "end", None
        if envelope.get("type") == "turn.interrupt":
            return "interrupt", _played_ms(envelope)
        if envelope.get("type") == "session.activate":
            on_activate()


def _played_ms(envelope: dict) -> int | None:
    """The `played_ms` a barge-in reports, when the client sent a usable one."""
    value = envelope.get("played_ms")
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
        return int(value)
    return None


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
