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
            # Nobody ended this call: the tab was closed, or the connection
            # dropped. The training still happened and its Turns are in memory,
            # so it is stored -- as `aborted`, never as `completed` (ADR 0034's
            # amendment). ADR 0034 originally discarded it; that threw away ten
            # minutes of training for a network blip, and storing it as
            # completed instead -- which is what the swallowed disconnect in
            # `_receive_json` used to do -- counted a walked-away call as a
            # finished one in the history and the activity calendar.
            #
            # Three exception types, because a lost connection looks different
            # depending on which side noticed. The receive side raises
            # WebSocketDisconnect. A *send* into a socket the client already
            # dropped raises uvicorn's ClientDisconnected, which subclasses
            # OSError -- caught by its base rather than by importing a server
            # internal -- or RuntimeError ("send after close") once the close
            # has been processed. Only the first was caught here, so a
            # disconnect that surfaced on the send side tore the handler down
            # and lost the Session entirely, which is the state the amendment
            # exists to remove. The same insight is already written out 30
            # lines below, for the final send.
            #
            # The breadth is deliberate and its cost is bounded: anything else
            # reaching here is stored as an aborted Session and logged with its
            # type, where it used to be an unhandled error and a lost training.
            logger.warning("Session ended without a client (%s: %s); storing it as aborted",
                           type(e).__name__, e)
            reason = "disconnected"

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
        orchestrator.close()  # a notes refresh still in flight has no reader (ADR 0071)
        try:
            await websocket.send_json({"type": "session.ended", "reason": reason, "transcript": transcript})
            await websocket.close()
        except (WebSocketDisconnect, RuntimeError):
            # The client can drop before this final send; Starlette then raises
            # RuntimeError ("send after close"), not WebSocketDisconnect. The
            # transcript is lost with the connection, but the Session itself is
            # not: `_record` above has already written it (ADR 0034's
            # amendment), so it is readable from the history.
            logger.info("Client disconnected before session.ended could be sent")
            return
        logger.info("Session ended (%s)", reason)


async def _record(  # pylint: disable=too-many-arguments,too-many-positional-arguments
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
    # Consent is checked inside `persist_session`'s own transaction (ADR 0066),
    # not here: it is the last point at which unconsented data can be prevented
    # from existing, and the check only holds if it commits with the write it
    # authorises. Asked from out here it was minutes newer than the handshake
    # and still milliseconds older than the INSERT. `None` means it said no and
    # nothing was written. The call itself is unaffected either way — the
    # transcript has already been sent.
    try:
        db_id = await asyncio.to_thread(
            persistence.persist_session,
            session_id, subject_id, persona, scenario, orchestrator.turns, started_at, reason,
        )
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Session could not be persisted; it is lost")
        return
    if db_id is None:
        return
    try:
        # Imported here, not at module scope: the live path must not need
        # Redis to be importable, let alone reachable. `jobs` stays at module
        # scope -- it touches only the database, and the handler below needs it
        # bound even when this import is what failed.
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


async def _session_start_frame(websocket: WebSocket) -> dict | None:
    """The first frame, if it is the `session.start` object the protocol asks
    for. Otherwise None, with the socket closed -- except on a disconnect,
    where there is nothing left to close.

    Every shape the socket can carry needs an answer here, because all of this
    is reachable before anything has been authenticated: a binary frame reads
    as a KeyError (Starlette passes the ASGI message through, and it carries
    "bytes" rather than "text"), text that is not JSON as a decode error, and a
    JSON scalar or array parses and then has no `.get()`. Each of those used to
    leave the handler on an unhandled exception.
    """
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
    Session. Anything else is handled and the wait continues: a frame that is
    not a control message at all, an unrecognised type (client and server
    versions need not match exactly), `session.activate`, and the barge-in over
    the tail of a reply that had already finished on this side -- the server
    streams audio ahead of playback, so that interrupt lands here, between
    turns, and trims the just-finished reply to what was heard (ADR 0035).
    """
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
    """Session runs until the user ends the session, a turn fails, or the
    persona ends the call naturally ("user", "error", or "completed").

    Takes `on_activate` for the same reason _wait_for_control_message does:
    session.activate lands in whichever receive loop happens to own the socket
    at that moment. The opening turn is usually already forwarded by the time
    the user leaves the mic check, so that is normally this loop, not that one.
    """
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
            # A barge-in over the tail of the reply that ended the call: the
            # goodbye is in the history and the decision stands. Carrying on
            # here ran a whole further Turn, and a second goodbye, on a call
            # that was already over (ADR 0035).
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
            # The client went away while this was parked in its receive. The
            # turn still has to be torn down before that travels on: left
            # alone, the forwarder outlives this handler and goes on mutating
            # `orchestrator.turns` while `_record` reads the same list from a
            # worker thread, and the turn generator stays parked at its yield
            # inside the TTS stream -- whose `finally` is what drops the pooled
            # KugelAudio socket, so it would be dropped by the garbage
            # collector instead of now (ADR 0044's amendment).
            await _tear_down_turn(forward_task, events)
            raise
        # Hand the played-through position to the orchestrator before *any* of
        # the teardown below, because either half of it can finalize the turn.
        # Cancelling forward_task delivers the CancelledError into whatever it
        # is suspended in -- and while the reply is being generated that is the
        # turn generator itself, parked on the TTS gateway, whose own handler
        # then runs _finalize_interrupted immediately. That is the common case:
        # synthesis is a network round trip, forwarding a chunk to the socket is
        # not. Setting the position after the cancel therefore lost it exactly
        # when it mattered, and the finalizer fell back to committing every
        # dispatched chunk -- the behaviour ADR 0035 exists to prevent.
        if kind == "interrupt":
            on_barge_in(played_ms)
        await _tear_down_turn(forward_task, events)
        if kind == "interrupt":
            logger.info("User barged in (played %s ms of the reply)", played_ms)
            await websocket.send_json({"type": "state", "value": "listening"})
            return "interrupted"
        return "user"

    # forward_task finished first. control_task is almost always still parked in
    # its receive, but a barge-in over the tail of a reply that just completed
    # can land in the gap between the wait returning and this cancel -- in which
    # case control_task resolves with the interrupt instead of raising. Honour
    # it, or the played-through position is lost and the whole reply stays in
    # the transcript (ADR 0035).
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

    Cancelling delivers the CancelledError into whatever the forwarder is
    suspended in, which while a reply is being generated is the turn generator
    itself. Where it was suspended in a socket send instead, the cancel unwinds
    only the forwarder and leaves the generator parked at its yield, which is
    what `aclose` is for."""
    forward_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await forward_task
    await events.aclose()


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

    A disconnect is *not* caught here. Swallowing it made the caller read a
    dropped connection as the user pressing "end call", and the Session was
    stored as completed -- the one thing ADR 0034 says it must not be. It now
    travels up to `session_ws`, which is the only place that knows how a call
    that nobody ended is stored.

    Everything else the socket can carry answers None, and the callers skip it
    the way they skip an unknown message type. Three shapes got past the old
    guard and tore the whole handler down mid-call -- no `_record`, no
    `session.ended`, the training gone: a binary frame where a control message
    was expected (Starlette hands the ASGI message through and it carries
    "bytes", not "text", so reading it is a KeyError), and a JSON scalar or
    array, which parses cleanly and then has no `.get()`.
    """
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
