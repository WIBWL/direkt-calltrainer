"""REST route for a finished Session: its Transcript, statistics and Feedback.

The Feedback is generated asynchronously (ADR 0019), so the Session becomes
readable before its wrap-up exists. `status` says which of the two states the
client is looking at, and the client polls until it settles.

Measurements sit next to the Turns rather than inside them: each one describes
the whole call (ADR 0051). What stays per Turn is the Transcript itself, with
the offset that makes it a timestamped transcript.

A Session is addressed by its `extern_id`, never by its primary key
(ADR 0050), and is readable only by the User whose `sub` is on the row
(ADR 0031). A Session owned by someone else answers 404 and not 403: a 403
would confirm that the id exists, which is exactly what the unguessable id is
there to withhold. A sequential key could offer neither guarantee.

`POST /api/sessions/{extern_id}/follow-up` (F-60) is the second route: the same
Session, read for what its Feedback asked the User to work on, handed to
`backend/followups.py` to design the next exercise from. It stores nothing.

The wire matches the schema (ADR 0057): the dicts below pass the ORM's own
English column values straight through to frontend/src/protocol.ts, with no
translation step.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from openai import OpenAIError
from sqlalchemy.orm import selectinload

from backend.auth import AuthContext, require_user
from backend.db import models as db_models
from backend.db.session import session_scope
from backend.followups import FollowUpError, draft_follow_up

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", dependencies=[Depends(require_user)])


@router.get("/{extern_id}")
def get_session(extern_id: uuid.UUID, caller: AuthContext = Depends(require_user)) -> dict:
    """One finished Session: Transcript, measurements, Feedback."""
    with session_scope() as db:
        session = (
            db.query(db_models.Session)
            .filter_by(extern_id=extern_id)
            .options(
                selectinload(db_models.Session.turns),
                selectinload(db_models.Session.measurements)
                .selectinload(db_models.Measurement.metric_type),
                selectinload(db_models.Session.feedback)
                .selectinload(db_models.Feedback.points),
                selectinload(db_models.Session.jobs),
                selectinload(db_models.Session.persona),
                selectinload(db_models.Session.scenario),
            )
            .one_or_none()
        )
        # Absent and not-yours are deliberately the same answer: anything
        # else would confirm that an id exists (ADR 0050).
        if session is None or session.subject_id != caller.sub:
            raise HTTPException(status_code=404, detail="Unknown session")
        return {
            "session_id": str(session.extern_id),
            "persona": session.persona.name,
            "scenario": session.scenario.title,
            "status": _feedback_status(session),
            "turns": [_turn(t) for t in sorted(session.turns, key=lambda t: t.seq_index)],
            "measurements": [_measurement(m) for m in session.measurements],
            "feedback": _feedback(session.feedback),
        }


@router.post("/{extern_id}/follow-up")
async def create_follow_up(
    extern_id: uuid.UUID, caller: AuthContext = Depends(require_user)
) -> dict:
    """A Scenario draft built from what this Session's Feedback asked for (F-60).

    Stores nothing: it opens in the editor and is saved, if at all, through the
    ordinary authoring route (ADR 0064). The improvement points are the whole
    input, so a Session without them has nothing to build from (409).

    `session_scope()` is synchronous, so the read goes to a thread — this route
    is `async def` for the model call and must not block the event loop.
    """
    material = await asyncio.to_thread(_follow_up_material, extern_id, caller.sub)
    # Absent and not-yours stay the same answer as in `get_session` (ADR 0050).
    if material is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    if not material.has_feedback:
        raise HTTPException(
            status_code=409,
            detail="Das Feedback zu diesem Gespräch ist noch nicht fertig.",
        )
    if not material.improvements:
        raise HTTPException(
            status_code=409,
            detail=(
                "Dieses Feedback nennt keine Verbesserungspunkte, aus denen sich "
                "ein Folgeszenario bauen ließe."
            ),
        )

    try:
        return await draft_follow_up(
            material.scenario_name,
            material.scenario_teaser,
            material.improvements,
            material.phase_language,
        )
    except (OpenAIError, FollowUpError) as e:
        # A dead gateway and an unparseable reply are the same thing from here.
        logger.warning("Follow-up draft failed for session %s: %s", extern_id, e)
        raise HTTPException(
            status_code=503,
            detail=(
                "Das Folgeszenario konnte gerade nicht erstellt werden. "
                "Bitte später noch einmal versuchen."
            ),
        ) from e


@dataclass(frozen=True)
class _FollowUpMaterial:
    """What the follow-up prompt is built from, read out before the database
    handle is gone. The Scenario's card only, never its prompt fields."""

    scenario_name: str
    scenario_teaser: str
    has_feedback: bool
    improvements: list[str]
    phase_language: str | None


def _follow_up_material(extern_id: uuid.UUID, subject: str) -> _FollowUpMaterial | None:
    """This Session's material, or None if it is not the caller's."""
    with session_scope() as db:
        session = (
            db.query(db_models.Session)
            .filter_by(extern_id=extern_id)
            .options(
                selectinload(db_models.Session.scenario),
                selectinload(db_models.Session.feedback)
                .selectinload(db_models.Feedback.points),
            )
            .one_or_none()
        )
        if session is None or session.subject_id != subject:
            return None
        feedback = session.feedback
        return _FollowUpMaterial(
            scenario_name=session.scenario.title,
            scenario_teaser=session.scenario.short_description,
            has_feedback=feedback is not None,
            improvements=[
                point.text
                for point in (feedback.points if feedback else [])
                if point.kind == db_models.POINT_IMPROVEMENT
            ],
            phase_language=feedback.phase_language if feedback else None,
        )


def _feedback_status(session: db_models.Session) -> str:
    """queued / running / done / failed, from the newest feedback job (ADR 0032).

    The job row is written in the same transaction as the Session, so its
    absence means nothing will ever generate a wrap-up -- which is "failed"
    from the client's side, and saves it a fifth status to handle.
    """
    jobs = [j for j in session.jobs if j.kind == db_models.JOB_KIND_FEEDBACK]
    if not jobs:
        return db_models.JOB_FAILED
    job = max(jobs, key=lambda j: j.job_id)
    return db_models.JOB_FAILED if _abandoned(job) else job.status


def _abandoned(job: db_models.AnalysisJob) -> bool:
    """True for a `running` row that has not moved in longer than a job may run.

    The worker holding it is gone -- killed, timed out, or restarted -- and
    nothing will ever move the row off `running`, which is the gap ADR 0032
    names. Read as failed rather than left spinning; the row itself is not
    touched, because this is the reader's judgement and not a repair.
    """
    if job.status != db_models.JOB_RUNNING:
        return False
    # Imported here so importing the REST layer never requires Redis, the same
    # reason the live path defers it. JOB_TIMEOUT_S is what bounds a job's run,
    # so it is also what makes one provably over.
    from backend.feedback.queue import JOB_TIMEOUT_S  # pylint: disable=import-outside-toplevel

    updated = job.updated_at
    # A timestamptz reads back tz-aware, but comparing an aware and a naive
    # datetime raises -- and a 500 here would cost the user a wrap-up that
    # exists.
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=UTC)
    return datetime.now(UTC) - updated > timedelta(seconds=JOB_TIMEOUT_S)


def _turn(turn: db_models.Turn) -> dict:
    return {
        "turn_id": turn.turn_id,
        "speaker": turn.speaker,
        "start_offset_ms": turn.start_offset_ms,
        "duration_ms": turn.duration_ms,
        "transcript": turn.transcript,
    }


def _measurement(measurement: db_models.Measurement) -> dict:
    return {
        "key": measurement.metric_type.key,
        "name": measurement.metric_type.name,
        "unit": measurement.metric_type.unit,
        "value": float(measurement.value),
        "detail": measurement.detail_json,
    }


def _feedback(feedback: db_models.Feedback | None) -> dict | None:
    if feedback is None:
        return None
    return {
        "summary": feedback.summary,
        # NULL where the wrap-up carries no phase analysis (F-42) -- an older
        # Session, or one whose model answer fell back to narrative only. The
        # frontend drops the block rather than showing an empty one.
        "phase_language": feedback.phase_language,
        "points": [
            {"kind": p.kind, "text": p.text, "turn_id": p.turn_id}
            for p in feedback.points
        ],
    }
