"""Stored-Session routes: history, detail with the polled wrap-up, retry, and the
follow-up/reverse (ADR 0100). A foreign id answers 404, never 403 (ADR 0050)."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from openai import OpenAIError
from sqlalchemy.orm import Session as DbSession, selectinload

from shared.db import models as db_models
from shared.db.session import session_scope
from shared.feedback import jobs
from backend import deletion, library
from backend.api import served
from backend.api._loading import FOR_RETRY, SESSION_SUBTREE, WITH_WRAPUP, owned_session
from backend.api.deps import current_tenant_id
from backend.auth import AuthContext, require_user
from backend.followups import FollowUpError, PlayedCall, draft_follow_up
from backend import limits
from backend.reversals import ReverseError, draft_brief

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", dependencies=[Depends(require_user)])

# The cap stops one request loading a heavy user's whole past.
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


@router.get("")
def list_sessions(
    caller: AuthContext = Depends(require_user),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
) -> dict:
    """Ownership is the query itself (ADR 0064)."""
    with session_scope() as db:
        query = (
            db.query(db_models.Session)
            .filter_by(subject_id=caller.sub)
            .options(
                selectinload(db_models.Session.measurements)
                .selectinload(db_models.Measurement.metric_type),
                selectinload(db_models.Session.persona),
                selectinload(db_models.Session.scenario),
                # Down to the focus goal, or a page costs a query per tagged point.
                selectinload(db_models.Session.feedback)
                .selectinload(db_models.Feedback.points)
                .selectinload(db_models.FeedbackPoint.focus_goal),
                selectinload(db_models.Session.jobs),
            )
        )
        # Before the slice: the client needs to know whether more pages exist.
        total = query.order_by(None).count()
        sessions = (
            # session_id breaks ties on started_at, or rows appear on two pages or none.
            query.order_by(
                db_models.Session.started_at.desc(),
                db_models.Session.session_id.desc(),
            )
            .limit(limit)
            .offset(offset)
            .all()
        )
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "sessions": [served.summary(s) for s in sessions],
        }


@router.get("/{extern_id}")
def get_session(extern_id: uuid.UUID, caller: AuthContext = Depends(require_user)) -> dict:
    with session_scope() as db:
        session = owned_session(
            db, caller.sub, extern_id,
            *SESSION_SUBTREE,
            selectinload(db_models.Session.jobs),
            selectinload(db_models.Session.findings),
        )
        if session is None:
            raise HTTPException(status_code=404, detail="Unknown session")
        return served.detail(session, follow_up=_follow_up(db, session.session_id))


@router.delete("/{extern_id}", status_code=204, response_class=Response)
def delete_one_session(
    extern_id: uuid.UUID, caller: AuthContext = Depends(require_user)
) -> Response:
    """A second DELETE is a 404 too, on purpose."""
    with session_scope() as db:
        if not deletion.delete_session(db, caller.sub, extern_id):
            raise HTTPException(status_code=404, detail="Unknown session")
    # Explicit: FastAPI would derive a body model from an annotation, and 204 has none.
    return Response(status_code=204)


# The sentences per refusal; `jobs` decides whether, this module speaks to the User.
_RETRY_REFUSALS = {
    jobs.BLOCKED_DONE: "Für dieses Gespräch liegt bereits eine Auswertung vor.",
    jobs.BLOCKED_EMPTY: (
        "In diesem Gespräch wurde nichts aufgezeichnet, das sich auswerten ließe."
    ),
    jobs.BLOCKED_WORKING: (
        "Die Auswertung wird gerade erstellt. Bitte warten Sie einen Moment."
    ),
}


@router.post("/{extern_id}/feedback", status_code=202)
def retry_feedback(
    extern_id: uuid.UUID, caller: AuthContext = Depends(require_user)
) -> dict:
    """Written from stored data, never audio (ADR 0049). 503 leaves the job row
    untouched, so the screen keeps showing the failure rather than a spinner."""
    with session_scope() as db:
        session = owned_session(db, caller.sub, extern_id, *FOR_RETRY)
        if session is None:
            raise HTTPException(status_code=404, detail="Unknown session")

        blocked = jobs.retry_blocked(session)
        if blocked is not None:
            raise HTTPException(status_code=409, detail=_RETRY_REFUSALS[blocked])

        session_pk = session.session_id
        # Imported here, so the REST layer does not need Redis.
        from shared.feedback import queue  # pylint: disable=import-outside-toplevel

        try:
            queue.enqueue_feedback(session_pk)
        except Exception as e:
            logger.warning("Could not queue a wrap-up for session %s: %s", extern_id, e)
            raise HTTPException(
                status_code=503,
                detail=(
                    "Die Auswertung kann gerade nicht angefordert werden. "
                    "Bitte später noch einmal versuchen."
                ),
            ) from e

        # Only after the queue took it, or the row lies.
        jobs.mark(db, session_pk, db_models.JOB_QUEUED)

    return {"status": db_models.JOB_QUEUED}


# Pinned to the client's `MIN_USER_TURNS` by test_reverse.py; this enforces it.
MIN_USER_UTTERANCES = 3


def _user_utterances(db: DbSession, session_pk: int) -> int:
    """One row per speaker, so the Persona's lines are not counted."""
    return (
        db.query(db_models.Turn)
        .filter(
            db_models.Turn.session_id == session_pk,
            db_models.Turn.speaker == db_models.SPEAKER_USER,
        )
        .count()
    )


def _too_short(what: str) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail=f"In diesem Gespräch wurde zu wenig gesprochen, um daraus {what} zu bauen.",
    )


@router.post("/{extern_id}/reverse")
async def create_reverse(
    extern_id: uuid.UUID,
    caller: AuthContext = Depends(require_user),
    tenant_id: int = Depends(current_tenant_id),
) -> dict:
    """F-61. Idempotent; a reverse of a reverse is refused. No consent guard:
    without consent there is no stored Session (ADR 0066)."""
    material = await asyncio.to_thread(_reverse_material, extern_id, caller.sub)
    if material is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    if material.already_reverse:
        raise HTTPException(
            status_code=409,
            detail="Dieses Gespräch ist selbst schon ein Rollentausch.",
        )
    if material.user_utterances < MIN_USER_UTTERANCES:
        raise _too_short("einen Rollentausch")

    existing = await asyncio.to_thread(library.restore_reverse, material.session_pk)
    if existing is not None:
        return _reverse_response(existing)
    limits.enforce(limits.SCENARIO_DRAFTS, caller.sub)  # only a drafted one counts

    try:
        brief = await draft_brief(
            material.description,
            material.case_facts,
            material.call_goal,
            material.improvements,
        )
    except (OpenAIError, ReverseError) as e:
        logger.warning("Reverse briefing failed for session %s: %s", extern_id, e)
        raise HTTPException(
            status_code=503,
            detail=(
                "Der Rollentausch konnte gerade nicht vorbereitet werden. "
                "Bitte später noch einmal versuchen."
            ),
        ) from e

    scenario = await asyncio.to_thread(
        library.create_reverse, material.session_pk, caller.sub, tenant_id, brief
    )
    if scenario is None:
        # Deleted meanwhile in another tab; nothing was written.
        raise HTTPException(status_code=404, detail="Unknown session")
    return _reverse_response(scenario)


def _reverse_response(scenario) -> dict:
    return {
        "id": scenario.id,
        "name": scenario.name,
        "short_description": scenario.short_description,
        "reverse_brief": scenario.reverse_brief,
    }


@dataclass(frozen=True)
class _ReverseMaterial:
    """Includes the played prompt fields, the exception ADR 0070 takes to ADR 0043."""

    session_pk: int
    already_reverse: bool
    user_utterances: int
    description: str
    case_facts: str
    call_goal: str
    improvements: list[str]


def _reverse_material(extern_id: uuid.UUID, subject: str) -> _ReverseMaterial | None:
    with session_scope() as db:
        session = owned_session(db, subject, extern_id, *WITH_WRAPUP)
        if session is None:
            return None
        scenario = session.scenario
        feedback = session.feedback
        return _ReverseMaterial(
            session_pk=session.session_id,
            already_reverse=scenario.reverse,
            user_utterances=_user_utterances(db, session.session_id),
            description=scenario.description,
            case_facts=scenario.case_facts,
            call_goal=scenario.call_goal,
            # May be empty: the coaching points only order the goals.
            improvements=[
                point.text
                for point in (feedback.points if feedback else [])
                if point.kind == db_models.POINT_IMPROVEMENT
            ],
        )


@router.post("/{extern_id}/follow-up")
async def create_follow_up(
    extern_id: uuid.UUID,
    caller: AuthContext = Depends(require_user),
    tenant_id: int = Depends(current_tenant_id),
) -> dict:
    """F-60, shaped like the reverse route. 409 when the wrap-up names no
    improvement points."""
    material = await asyncio.to_thread(_follow_up_material, extern_id, caller.sub)
    if material is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    if material.user_utterances < MIN_USER_UTTERANCES:
        raise _too_short("ein Folgeszenario")
    if not material.call.improvements:
        raise HTTPException(
            status_code=409,
            detail=(
                "Diese Auswertung nennt keine Punkte zum Weiterentwickeln, "
                "aus denen sich eine Übung bauen ließe."
            ),
        )

    existing = await asyncio.to_thread(library.restore_follow_up, material.session_pk)
    if existing is not None:
        return _follow_up_response(existing)
    limits.enforce(limits.SCENARIO_DRAFTS, caller.sub)  # only a drafted one counts

    try:
        draft = await draft_follow_up(material.call)
    except (OpenAIError, FollowUpError) as e:
        logger.warning("Follow-up draft failed for session %s: %s", extern_id, e)
        raise HTTPException(
            status_code=503,
            detail=(
                "Das Folgeszenario konnte gerade nicht erstellt werden. "
                "Bitte später noch einmal versuchen."
            ),
        ) from e

    # Wire names to columns: the card's `name` is `title`.
    draft["title"] = draft.pop("name")
    scenario = await asyncio.to_thread(
        library.create_follow_up, draft, caller.sub, tenant_id, material.session_pk
    )
    if scenario is None:
        # Deleted meanwhile in another tab.
        raise HTTPException(status_code=404, detail="Unknown session")
    return _follow_up_response(scenario)


def _follow_up_response(scenario) -> dict:
    """The same shape `_follow_up` serves on the detail route."""
    return {
        "id": scenario.id,
        "name": scenario.name,
        "short_description": scenario.short_description,
    }


@dataclass(frozen=True)
class _FollowUpMaterial:
    """Statistics stay out (ADR 0051)."""

    session_pk: int
    user_utterances: int
    call: PlayedCall


def _follow_up_material(extern_id: uuid.UUID, subject: str) -> _FollowUpMaterial | None:
    """A missing wrap-up yields no improvements, refused like an empty one."""
    with session_scope() as db:
        session = owned_session(db, subject, extern_id, *WITH_WRAPUP)
        if session is None:
            return None
        scenario = session.scenario
        feedback = session.feedback
        return _FollowUpMaterial(
            session_pk=session.session_id,
            user_utterances=_user_utterances(db, session.session_id),
            call=PlayedCall(
                scenario_name=scenario.title,
                scenario_teaser=scenario.short_description,
                description=scenario.description,
                case_facts=scenario.case_facts,
                call_goal=scenario.call_goal,
                outcome=feedback.summary if feedback else "",
                improvements=tuple(
                    point.text
                    for point in (feedback.points if feedback else [])
                    if point.kind == db_models.POINT_IMPROVEMENT
                ),
                phase_language=feedback.phase_language if feedback else None,
            ),
        )


def _follow_up(db: DbSession, session_id: int) -> dict | None:
    """A query rather than a second mapped relationship between the two tables."""
    scenario = (
        db.query(db_models.Scenario)
        .filter_by(derived_from_session_id=session_id, active=True)
        .one_or_none()
    )
    if scenario is None:
        return None
    return {
        "id": str(scenario.extern_id),
        "name": scenario.title,
        "short_description": scenario.short_description,
    }
