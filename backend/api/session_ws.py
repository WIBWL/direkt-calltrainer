"""The `/ws/session` route between the wire protocol and `SessionOrchestrator`.
The token rides in the first message: browsers cannot set WebSocket headers."""

import asyncio
import contextlib
import json
import logging
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.exc import SQLAlchemyError

from shared.logging_config import session_id_scope
from shared.feedback import jobs
from shared.feedback.calls import utterances
from backend.auth import NOT_ADMITTED, AuthContext, authenticate_ws
from backend import limits
from backend.limits import MAX_CALL_S, MAX_TURN_AUDIO_BYTES
from backend.tenants import resolve_tenant_id
from backend import library
from backend.personas import Persona
from backend.scenarios import Scenario
from backend.session import persistence
from backend.session.events import AudioChunk, Failed, StateChanged, TurnCompleted, TurnEvent
from backend.session.orchestrator import SessionOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter()

# Until `session.start` nobody is known; a silent socket must not hold forever.
HANDSHAKE_TIMEOUT_S = 10.0

_TOO_MANY_CALLS = (
    "Sie führen bereits zu viele Gespräche gleichzeitig. Bitte beenden Sie "
    "zuerst ein anderes Gespräch."
)
_TIME_LIMIT = f"Das Gespräch wurde nach {MAX_CALL_S // 60} Minuten automatisch beendet."


@router.websocket("/ws/session")
async def session_ws(websocket: WebSocket) -> None:
    """JSON control messages; audio as a binary frame after its meta message."""
    await websocket.accept()

    handshake = await _handshake(websocket)
    if handshake is None:
        return
    persona, scenario, auth = handshake

    # Through the module, so tests can swap in fresh counters.
    slots = limits.OPEN_CALLS
    if not slots.claim(auth.sub):
        logger.warning("Handshake refused: subject=%s has too many open calls", auth.sub)
        await _refuse(websocket, "too_many_calls", _TOO_MANY_CALLS, "Too many open calls")
        return
    try:
        await _serve_call(websocket, persona, scenario, auth)
    finally:
        slots.release(auth.sub)


async def _serve_call(
    websocket: WebSocket, persona: Persona, scenario: Scenario, auth: AuthContext
) -> None:
    session_id = uuid.uuid4()
    started_at = datetime.now(UTC)
    deadline = asyncio.get_running_loop().time() + MAX_CALL_S
    with session_id_scope(str(session_id)):
        orchestrator = SessionOrchestrator(persona, scenario)
        logger.info(
            "Session started: subject=%s persona=%s language=%s", auth.sub, persona.id, persona.language_id
        )

        await websocket.send_json({"type": "session.started", "session_id": str(session_id)})

        try:
            outcome = await _open_call(websocket, orchestrator, scenario)
            if outcome == "interrupted" and orchestrator.ended:
                reason = "completed"  # talked over the goodbye; the ending stands
            elif outcome in ("ok", "interrupted"):
                reason = await _run_session(
                    websocket, orchestrator, orchestrator.start_playback, deadline=deadline
                )
            else:
                # "failed" is the Turn's word for what the client calls "error".
                reason = "error" if outcome == "failed" else outcome
        except (WebSocketDisconnect, RuntimeError, OSError) as e:
            # Nobody ended this call: stored as `aborted` (ADR 0034). A lost
            # connection shows as any of these three depending on the side.
            logger.warning("Session ended without a client (%s: %s); storing it as aborted",
                           type(e).__name__, e)
            reason = "disconnected"

        transcript = [
            {"speaker": u.speaker, "text": u.text, "offset_ms": u.offset_ms}
            for u in utterances(orchestrator.turns)
        ]
        # Before session.ended, so a 404 on the wrap-up means the write failed.
        await _record(persistence.FinishedCall(
            extern_id=session_id,
            subject_id=auth.sub,
            persona=persona,
            scenario=scenario,
            turns=orchestrator.turns,
            started_at=started_at,
            reason=reason,
        ))
        orchestrator.close()
        try:
            await websocket.send_json({"type": "session.ended", "reason": reason, "transcript": transcript})
            await websocket.close()
        except (WebSocketDisconnect, RuntimeError):
            # A gone client raises RuntimeError here; `_record` already stored it.
            logger.info("Client disconnected before session.ended could be sent")
            return
        logger.info("Session ended (%s)", reason)


async def _record(call: persistence.FinishedCall) -> None:
    """Off the event loop and never raises: no outage may cost the user their
    transcript. Consent is checked inside `persist_session` (ADR 0066)."""
    try:
        db_id = await asyncio.to_thread(persistence.persist_session, call)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Session could not be persisted; it is lost")
        return
    if db_id is None:
        return
    try:
        # Imported here: the live path must not need Redis to import.
        from shared.feedback import queue  # pylint: disable=import-outside-toplevel

        await asyncio.to_thread(queue.enqueue_feedback, db_id)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.exception("Feedback could not be queued for session %d", db_id)
        # Only this place knows the job was never received (ADR 0032).
        await asyncio.to_thread(jobs.mark_failed, db_id, str(e))


def _load_selection(
    persona_id: str | None, scenario_id: str | None, auth: AuthContext
) -> tuple[Persona | None, Scenario | None]:
    """In one worker thread; the Scenario is scoped to the caller's tenant."""
    persona = library.get_persona(persona_id)
    scenario = library.get_scenario(scenario_id, auth.sub, resolve_tenant_id(auth))
    return persona, scenario


async def _refuse(websocket: WebSocket, code: str, message: str, reason: str) -> None:
    """An `error` frame first: the close reason never reaches the call screen."""
    with contextlib.suppress(WebSocketDisconnect, RuntimeError, OSError):
        await websocket.send_json({"type": "error", "code": code, "message": message})
        await websocket.close(code=1008, reason=reason)


async def _session_start_frame(websocket: WebSocket) -> dict | None:
    """Reachable unauthenticated, so every shape is answered: binary, non-JSON,
    a JSON scalar, or silence past HANDSHAKE_TIMEOUT_S."""
    try:
        start = await asyncio.wait_for(websocket.receive_json(), HANDSHAKE_TIMEOUT_S)
    except WebSocketDisconnect:
        return None
    except TimeoutError:
        logger.warning("Handshake failed: no session.start within %.0f s", HANDSHAKE_TIMEOUT_S)
        await websocket.close(code=1008, reason="Expected session.start")
        return None
    except (KeyError, json.JSONDecodeError, TypeError):
        logger.warning("Handshake failed: first frame is not a JSON object")
        await websocket.close(code=1002, reason="Expected session.start")
        return None
    if isinstance(start, dict) and start.get("type") == "session.start":
        return start
    got = start.get("type") if isinstance(start, dict) else type(start).__name__
    logger.warning("Handshake failed: expected session.start, got %r", got)
    await websocket.close(code=1002, reason="Expected session.start")
    return None


async def _handshake(websocket: WebSocket) -> tuple[Persona, Scenario, AuthContext] | None:
    """None, with the socket closed, on any malformed, unauthenticated or unknown input."""
    start = await _session_start_frame(websocket)
    if start is None:
        return None

    # Off the event loop: verification may be a synchronous JWKS round trip.
    auth = await asyncio.to_thread(authenticate_ws, start)
    if auth is None:
        logger.warning("Handshake failed: missing or invalid token")
        await websocket.close(code=1008, reason="Authentication required")
        return None
    if not auth.admitted:
        logger.warning("Handshake refused: caller lacks the required role")
        await _refuse(websocket, "not_admitted", NOT_ADMITTED, "Not admitted")
        return None

    persona_id = start.get("persona_id")
    scenario_id = start.get("scenario_id")
    try:
        persona, scenario = await asyncio.to_thread(
            _load_selection, persona_id, scenario_id, auth
        )
    except SQLAlchemyError as e:
        # The library is unreachable: a server failure (1011), not a protocol error.
        logger.error("Handshake failed: could not read the library: %s", e)
        await websocket.close(code=1011, reason="Persona/scenario library unavailable")
        return None
    if persona is None or scenario is None:
        logger.warning("Handshake failed: unknown persona_id=%r/scenario_id=%r", persona_id, scenario_id)
        await websocket.close(code=1002, reason="Unknown persona_id/scenario_id")
        return None
    return persona, scenario, auth


# Literals, so a typo in a return or comparison is a type error.
_TurnResult = Literal["ok", "failed", "completed"]
_ControlMessage = Literal["end", "interrupt"]
# A barge-in carries the played ms (None from a client that reports none).
_Control = tuple[_ControlMessage, int | None]
_TurnOutcome = Literal["ok", "failed", "completed", "interrupted", "user"]
_SessionEndReason = Literal["user", "error", "completed"]


async def _open_call(
    websocket: WebSocket, orchestrator: SessionOrchestrator, scenario: Scenario
) -> _TurnOutcome:
    """Whoever picked up speaks first (ADR 0110). Ordinarily that is the user, and
    the client is told it is listening at once, because a VAD start in any other
    state reads as a barge-in. A reverse's Persona picks up with its pre-warmed
    opening (ADR 0042)."""
    if not scenario.reverse:
        await websocket.send_json({"type": "state", "value": "listening"})
        return "ok"
    return await _run_turn_interruptible(
        websocket,
        orchestrator.run_opening_turn(),
        orchestrator.start_playback,
        orchestrator.note_barge_in,
    )


# Not a client request: the line stayed silent after the pick-up (ADR 0110).
_SILENCE = "silence"


async def _next_turn_request(
    websocket: WebSocket, orchestrator: SessionOrchestrator, on_activate: Callable[[], None]
) -> dict | Literal["silence"] | None:
    """The next `turn.audio.meta`, None if the user ended it, or `_SILENCE`. A
    late barge-in lands here and trims the finished reply (ADR 0035)."""
    while True:
        envelope = await _receive_json_within(websocket, orchestrator.pickup_prompt_delay())
        if envelope == _SILENCE:
            return _SILENCE
        if envelope is None:
            continue
        kind = envelope.get("type")
        if kind == "session.end":
            return None
        if kind == "turn.audio.meta":
            return envelope
        if kind == "session.activate":
            on_activate()
        elif kind == "user.speaking":
            orchestrator.note_user_speaking()
        elif kind == "turn.interrupt":
            orchestrator.note_late_barge_in(_played_ms(envelope))


async def _receive_json_within(
    websocket: WebSocket, seconds: float | None
) -> dict | Literal["silence"] | None:
    """Timed by cancelling the receive, which loses no unreceived message."""
    if seconds is None:
        return await _receive_json(websocket)
    try:
        return await asyncio.wait_for(_receive_json(websocket), seconds)
    except TimeoutError:
        return _SILENCE


async def _run_session(
    websocket: WebSocket,
    orchestrator: SessionOrchestrator,
    on_activate: Callable[[], None],
    *,
    deadline: float,
) -> _SessionEndReason:
    """"user", "error", or "completed" (the Persona ended it, or the time limit
    passed between turns, ADR 0109)."""
    loop = asyncio.get_running_loop()
    while True:
        try:
            # Cancelling a receive is safe between turns.
            envelope = await asyncio.wait_for(
                _next_turn_request(websocket, orchestrator, on_activate),
                max(0.0, deadline - loop.time()),
            )
        except TimeoutError:
            logger.info("Call reached its %d-minute limit; ending it", MAX_CALL_S // 60)
            await websocket.send_json({"type": "error", "code": "time_limit", "message": _TIME_LIMIT})
            return "completed"
        if envelope is None:
            return "user"
        if envelope == _SILENCE:
            turn = orchestrator.run_pickup_prompt()
        else:
            audio_bytes = await _turn_audio(websocket)
            if audio_bytes is None:
                continue
            turn = orchestrator.run_turn(audio_bytes, "turn.webm", envelope.get("mime_type"))
        outcome = await _run_turn_interruptible(
            websocket, turn, orchestrator.start_playback, orchestrator.note_barge_in
        )
        if outcome == "interrupted":
            if orchestrator.ended:
                return "completed"
            continue
        if outcome != "ok":
            return "error" if outcome == "failed" else outcome


async def _turn_audio(websocket: WebSocket) -> bytes | None:
    audio_bytes = await _receive_bytes(websocket)
    if audio_bytes is None:
        # An out-of-step client: skip the turn, don't end the Session.
        logger.warning("Expected a binary audio frame after turn.audio.meta; skipping the turn")
        return None
    if len(audio_bytes) > MAX_TURN_AUDIO_BYTES:
        # Never sent to Whisper; the client is told to listen again.
        logger.warning("Turn audio of %d bytes over the %d-byte cap; skipping the turn",
                       len(audio_bytes), MAX_TURN_AUDIO_BYTES)
        await websocket.send_json({"type": "state", "value": "listening"})
        return None
    return audio_bytes


async def _run_turn_interruptible(
    websocket: WebSocket,
    events: AsyncIterator[TurnEvent],
    on_activate: Callable[[], None],
    on_barge_in: Callable[[int | None], None],
) -> _TurnOutcome:
    """Races the turn's events against session.end, disconnect and barge-in."""
    forward_task = asyncio.create_task(_forward_turn_events(websocket, events))
    control_task = asyncio.create_task(_wait_for_control_message(websocket, on_activate))
    done, _ = await asyncio.wait({forward_task, control_task}, return_when=asyncio.FIRST_COMPLETED)

    if control_task in done:
        try:
            kind, played_ms = control_task.result()
        except WebSocketDisconnect:
            # Tear down first, or the forwarder mutates the turns while `_record`
            # reads them.
            await _tear_down_turn(forward_task, events)
            raise
        # The played position before any teardown: the cancel finalizes the turn
        # at once, and without the position every chunk is committed (ADR 0035).
        if kind == "interrupt":
            on_barge_in(played_ms)
        await _tear_down_turn(forward_task, events)
        if kind == "interrupt":
            logger.info("User barged in (played %s ms of the reply)", played_ms)
            await websocket.send_json({"type": "state", "value": "listening"})
            return "interrupted"
        return "user"

    # A barge-in can land between the wait and this cancel; honour it.
    control_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        late = await control_task
        if late is not None and late[0] == "interrupt":
            on_barge_in(late[1])
    if forward_task.exception() is not None:
        # The forwarder failed (usually a send to a dropped socket), leaving the
        # generator parked at its yield.
        await events.aclose()
    return forward_task.result()


async def _tear_down_turn(forward_task: asyncio.Task, events: AsyncIterator[TurnEvent]) -> None:
    """Cancel the forwarder, then close the generator. The `finally` matters: a
    failed forwarder re-raises from the await."""
    forward_task.cancel()
    try:
        with contextlib.suppress(asyncio.CancelledError):
            await forward_task
    finally:
        await events.aclose()


async def _wait_for_control_message(
    websocket: WebSocket, on_activate: Callable[[], None]
) -> _Control:
    """session.end or a disconnect ends the turn; turn.interrupt is a barge-in.
    session.activate can arrive during a reverse's opening."""
    while True:
        envelope = await _receive_json(websocket)
        if envelope is None:
            continue
        if envelope.get("type") == "session.end":
            return "end", None
        if envelope.get("type") == "turn.interrupt":
            return "interrupt", _played_ms(envelope)
        if envelope.get("type") == "session.activate":
            on_activate()


def _played_ms(envelope: dict) -> int | None:
    value = envelope.get("played_ms")
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
        return int(value)
    return None


async def _forward_turn_events(
    websocket: WebSocket, events: AsyncIterator[TurnEvent]
) -> _TurnResult:
    """The only TurnEvent-to-wire mapping."""
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
    """None for anything not a JSON object. A disconnect is deliberately not
    caught: swallowed, it would store the Session as completed (ADR 0034)."""
    try:
        raw = await websocket.receive_text()
    except KeyError:
        logger.warning("Binary frame where a control message was expected; skipped")
        return None
    try:
        envelope = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    return envelope if isinstance(envelope, dict) else None


async def _receive_bytes(websocket: WebSocket) -> bytes | None:
    """None for a text frame; a disconnect propagates."""
    try:
        return await websocket.receive_bytes()
    except KeyError:
        return None
