"""The `/ws/session` route: wire protocol on one side, `SessionOrchestrator` on
the other. A WebSocket because audio streams both ways and the user can barge
in (ADR 0033/0035); the token rides in the first message, since a browser
cannot header a WebSocket (ADR 0009).
"""

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

from backend.auth import AuthContext, authenticate_ws
from backend.logging_config import session_id_scope
from backend.tenants import resolve_tenant_id
from backend import library
from backend.feedback import jobs
from backend.personas import Persona
from backend.scenarios import Scenario
from backend.session import persistence
from backend.feedback.calls import utterances
from backend.session.models import (
    AudioChunk,
    Failed,
    StateChanged,
    TurnCompleted,
    TurnEvent,
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
    started_at = datetime.now(UTC)
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
            if outcome == "interrupted" and orchestrator.ended:
                reason = "completed"  # talked over the goodbye; the ending stands (ADR 0035)
            elif outcome in ("ok", "interrupted"):
                reason = await _run_session(websocket, orchestrator, orchestrator.start_playback)
            else:
                # The opening Turn itself ended the Session: "failed" is the Turn
                # vocabulary for what the client is told as "error"; "completed"
                # and "user" carry over unchanged.
                reason = "error" if outcome == "failed" else outcome
        except (WebSocketDisconnect, RuntimeError, OSError) as e:
            # Nobody ended this call: store it as `aborted`, never `completed`
            # (ADR 0034's amendment). Three types because a lost connection shows
            # differently by side: WebSocketDisconnect on receive, uvicorn's
            # ClientDisconnected (an OSError) or RuntimeError ("send after close")
            # on send. Catching only the first loses the Session.
            logger.warning("Session ended without a client (%s: %s); storing it as aborted",
                           type(e).__name__, e)
            reason = "disconnected"

        # Same flattening as the persisted Turn rows, so the two cannot disagree.
        transcript = [
            {"speaker": u.speaker, "text": u.text, "offset_ms": u.offset_ms}
            for u in utterances(orchestrator.turns)
        ]
        # Before session.ended, so a 404 on the Feedback means the write
        # failed, not that the client was early.
        await _record(persistence.FinishedCall(
            extern_id=session_id,
            subject_id=auth.sub,
            persona=persona,
            scenario=scenario,
            turns=orchestrator.turns,
            started_at=started_at,
            reason=reason,
        ))
        orchestrator.close()  # a notes refresh still in flight has no reader (ADR 0071)
        try:
            await websocket.send_json({"type": "session.ended", "reason": reason, "transcript": transcript})
            await websocket.close()
        except (WebSocketDisconnect, RuntimeError):
            # A client gone before this send raises RuntimeError ("send after
            # close"), not WebSocketDisconnect; `_record` already stored it.
            logger.info("Client disconnected before session.ended could be sent")
            return
        logger.info("Session ended (%s)", reason)


async def _record(call: persistence.FinishedCall) -> None:
    """Persist the finished Session and queue its wrap-up (ADR 0034, ADR 0019).

    Off the event loop (the ORM is synchronous) and never raises: no database
    or Redis outage may cost the user their transcript.
    """
    # Consent is checked inside `persist_session`'s own transaction (ADR 0066):
    # only there does the check commit with the write it authorises. `None`
    # means it said no and nothing was written.
    try:
        db_id = await asyncio.to_thread(persistence.persist_session, call)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Session could not be persisted; it is lost")
        return
    if db_id is None:
        return
    try:
        # Imported here: the live path must not need Redis to be importable.
        # `jobs` stays at module scope because the handler needs it when this fails.
        from backend.feedback import queue  # pylint: disable=import-outside-toplevel

        await asyncio.to_thread(queue.enqueue_feedback, db_id)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.exception("Feedback could not be queued for session %d", db_id)
        # The row persist_session just wrote says "queued" for a job nobody
        # ever received. This is the only place that knows better, so it
        # records it rather than leaving the row lying (ADR 0032).
        await asyncio.to_thread(jobs.mark_failed, db_id, str(e))


def _load_selection(
    persona_id: str | None, scenario_id: str | None, auth: AuthContext
) -> tuple[Persona | None, Scenario | None]:
    """The Persona and Scenario the handshake names, read in one worker thread
    (nothing blocking may run on the event loop, ADR 0034).

    The Scenario is scoped to the caller and their tenant (ADR 0060); Personas
    are all built-ins and not scoped."""
    persona = library.get_persona(persona_id)
    scenario = library.get_scenario(scenario_id, auth.sub, resolve_tenant_id(auth))
    return persona, scenario


async def _session_start_frame(websocket: WebSocket) -> dict | None:
    """The first frame if it is a `session.start` object, else None with the
    socket closed (unless it disconnected).

    Reachable unauthenticated, so every shape needs an answer: a binary frame
    is a KeyError, non-JSON a decode error, a JSON scalar/array has no `.get()`."""
    try:
        start = await websocket.receive_json()
    except WebSocketDisconnect:
        return None
    except (KeyError, json.JSONDecodeError, TypeError):
        logger.warning("Handshake failed: first frame is not a JSON object")
        # Protocol Error (1002; https://websocket.org/reference/close-codes/)
        await websocket.close(code=1002, reason="Expected session.start")
        return None
    if isinstance(start, dict) and start.get("type") == "session.start":
        return start
    got = start.get("type") if isinstance(start, dict) else type(start).__name__
    logger.warning("Handshake failed: expected session.start, got %r", got)
    await websocket.close(code=1002, reason="Expected session.start")
    return None


async def _handshake(websocket: WebSocket) -> tuple[Persona, Scenario, AuthContext] | None:
    """Reads the required `session.start` message, closing the socket and
    returning None on any malformed, unauthenticated or unknown input."""
    start = await _session_start_frame(websocket)
    if start is None:
        return None

    # A browser can't set an Authorization header on a WebSocket, so the token
    # rides in the handshake message (ADR 0009). Off the event loop: verifying
    # it is a synchronous JWKS round trip, and this loop streams live audio.
    auth = await asyncio.to_thread(authenticate_ws, start)
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


async def _next_turn_request(
    websocket: WebSocket, orchestrator: SessionOrchestrator, on_activate: Callable[[], None]
) -> dict | None:
    """Handle control messages until one asks for a turn.

    Returns that `turn.audio.meta` envelope, or None when the user ended the
    Session. Unknown frames are skipped; a late barge-in (audio is streamed
    ahead of playback) lands here and trims the finished reply (ADR 0035)."""
    while True:
        envelope = await _receive_json(websocket)
        if envelope is None:
            continue
        kind = envelope.get("type")
        if kind == "session.end":
            return None
        if kind == "turn.audio.meta":
            return envelope
        if kind == "session.activate":
            on_activate()
        elif kind == "turn.interrupt":
            orchestrator.note_late_barge_in(_played_ms(envelope))


async def _run_session(
    websocket: WebSocket, orchestrator: SessionOrchestrator, on_activate: Callable[[], None]
) -> _SessionEndReason:
    """Run until the user ends the session ("user"), a turn fails ("error") or
    the persona ends the call ("completed").

    Takes `on_activate` because session.activate lands in whichever receive
    loop owns the socket at that moment -- usually this one."""
    while True:
        envelope = await _next_turn_request(websocket, orchestrator, on_activate)
        if envelope is None:
            return "user"

        audio_bytes = await _receive_bytes(websocket)
        if audio_bytes is None:
            # The meta message promised a blob and a text frame arrived. An
            # out-of-step client is the same class of problem as the unknown
            # message type above, so the turn is skipped rather than the
            # Session ended.
            logger.warning("Expected a binary audio frame after turn.audio.meta; skipping the turn")
            continue

        turn = orchestrator.run_turn(audio_bytes, "turn.webm", envelope.get("mime_type"))
        outcome = await _run_turn_interruptible(
            websocket, turn, orchestrator.start_playback, orchestrator.note_barge_in
        )
        if outcome == "interrupted":
            # A barge-in over the goodbye: the call is still over (ADR 0035).
            if orchestrator.ended:
                return "completed"
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
        try:
            kind, played_ms = control_task.result()
        except WebSocketDisconnect:
            # Tear the turn down before re-raising: otherwise the forwarder keeps
            # mutating `orchestrator.turns` while `_record` reads it, and the
            # pooled KugelAudio socket is dropped by the GC, not now (ADR 0044).
            await _tear_down_turn(forward_task, events)
            raise
        # Hand over the played position *before* any teardown: the cancel
        # usually lands in the turn generator (parked on TTS), which finalizes
        # the turn at once. Set afterwards, the position is lost and every
        # dispatched chunk is committed -- what ADR 0035 exists to prevent.
        if kind == "interrupt":
            on_barge_in(played_ms)
        await _tear_down_turn(forward_task, events)
        if kind == "interrupt":
            logger.info("User barged in (played %s ms of the reply)", played_ms)
            await websocket.send_json({"type": "state", "value": "listening"})
            return "interrupted"
        return "user"

    # forward_task finished first, but a barge-in can land between the wait
    # and this cancel; honour it, or the whole reply stays in the transcript
    # (ADR 0035).
    control_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        late = await control_task
        if late is not None and late[0] == "interrupt":
            on_barge_in(late[1])
    if forward_task.exception() is not None:
        # The forwarder did not finish, it failed -- a send into a socket the
        # client had already dropped is the usual way. The generator is then
        # still parked at its yield and has to be closed here; on the ordinary
        # path it has run to exhaustion and this is skipped.
        await events.aclose()
    return forward_task.result()


async def _tear_down_turn(forward_task: asyncio.Task, events: AsyncIterator[TurnEvent]) -> None:
    """Stop forwarding this turn and close its generator, in that order.
    `aclose` covers a forwarder cancelled inside a socket send, which leaves the
    generator parked at its yield. The `finally` is load-bearing: a forwarder
    that already failed re-raises from `await forward_task`, and without it the
    loop's finaliser logs ERROR noise on every disconnect (ADR 0055)."""
    forward_task.cancel()
    try:
        with contextlib.suppress(asyncio.CancelledError):
            await forward_task
    finally:
        await events.aclose()


async def _wait_for_control_message(
    websocket: WebSocket, on_activate: Callable[[], None]
) -> _Control:
    """Wait for a message that interrupts the in-flight turn: session.end or a
    disconnect ends it, turn.interrupt is a barge-in (with played ms, ADR 0035).
    session.activate usually arrives during the opening turn (ADR 0051); it
    starts the clock and the wait continues.
    """
    while True:
        envelope = await _receive_json(websocket)
        if envelope is None:
            continue  # not a control message at all; keep waiting for one
        if envelope.get("type") == "session.end":
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
    """Receives one JSON control message, or None for anything that is not one.
    A disconnect is deliberately *not* caught: swallowed, it reads as the user
    ending the call and the Session is stored as completed (ADR 0034). A binary
    frame (KeyError) and a JSON scalar or array (no `.get()`) answer None, since
    either would otherwise tear the handler down mid-call."""
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
    """Receives one binary audio frame, or None when the client sent a text
    frame instead. A disconnect propagates, as above."""
    try:
        return await websocket.receive_bytes()
    except KeyError:
        return None
