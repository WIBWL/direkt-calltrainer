"""REST routes for finished Sessions: the caller's history, and one Session's
Transcript, statistics and Feedback.

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

Two routes here build a Scenario out of a finished Session, and both are asked
for rather than volunteered. `POST /{extern_id}/follow-up` (F-60, ADR 0069)
drafts the *next* exercise from the wrap-up's improvement points;
`POST /{extern_id}/reverse` (F-61, ADR 0070) copies the case that was played
into a Scenario that replays it with the roles swapped. They share their shape
on purpose — 404 for an unknown or foreign Session, 409 for one there is
nothing to build from, 503 for a model that would not answer, and idempotency
through a UNIQUE column, so pressing the button twice costs no second model
call. Both are here rather than under `/api/scenarios` because a Session is
what they are built from; the detail route carries the card of whichever
already exists.

The wire matches the schema (ADR 0057): the dicts below pass the ORM's own
English column values straight through to frontend/src/protocol.ts, with no
translation step.
"""

# pylint: disable=duplicate-code
# `_feedback` here and in the sibling route look alike and are not the same: the
# export serves `created_at` and plain points, the detail route `turn_id` and the
# focus goal. Two wire contracts -- merging them would need a flag, and a
# serializer with a flag is worse than two honest ones.


from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from openai import OpenAIError
from sqlalchemy.orm import Session as DbSession, selectinload

from backend import deletion, library
from backend.api._loading import SESSION_SUBTREE
from backend.api.deps import current_tenant_id
from backend.auth import AuthContext, require_user
from backend.db import models as db_models
from backend.db.session import session_scope
from backend.feedback import interruptions, intonation, metrics
from backend.followups import FollowUpError, PlayedCall, draft_follow_up
from backend.reversals import ReverseError, draft_brief

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", dependencies=[Depends(require_user)])

# Page size for the history. The default is what one screen of history shows;
# the cap is what keeps a single request from loading a heavy user's whole
# past, since the trend view asks for as much as it is allowed.
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


@router.get("")
def list_sessions(
    caller: AuthContext = Depends(require_user),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
) -> dict:
    """The caller's own finished Sessions, newest first (F-13/F-48).

    Filtered by `subject_id` and by nothing else: there is no route to anyone
    else's history, and no id to guess at, because ownership is the query here
    rather than a check applied after one (ADR 0031). That column is indexed
    for exactly this query -- see migration 18f5098dfb1b.

    Carries each Session's Measurements, which is what makes one request serve
    both screens: the history list reads the metadata, the progress view reads
    the values as one point per Session (ADR 0051 already guarantees exactly
    one per metric). `detail_json` is deliberately dropped -- the loudness
    curve alone is larger than everything else here put together, and no view
    over several Sessions plots it.

    What it does not carry is the wrap-up text -- that stays on the detail
    route. It does say whether one exists, under a name of its own: `status`
    here is `session.status` (ADR 0057) and must keep meaning that, so the
    wrap-up's state is `feedback_status` and never `status`.
    """
    with session_scope() as db:
        query = (
            db.query(db_models.Session)
            .filter_by(subject_id=caller.sub)
            .options(
                selectinload(db_models.Session.measurements)
                .selectinload(db_models.Measurement.metric_type),
                selectinload(db_models.Session.persona),
                selectinload(db_models.Session.scenario),
                # Two more queries per page, not two per row: selectinload
                # batches them, so the wrap-up flag costs the same at 20 rows
                # as at one.
                #
                # The points and their goal hang off the same load for the same
                # reason. `_feedback_goals` walks both, so without this a page
                # of 20 wrap-ups costs a query per wrap-up plus one per tagged
                # point -- the shape that looks fine on a developer's three
                # Sessions and not on six months of them.
                selectinload(db_models.Session.feedback)
                .selectinload(db_models.Feedback.points)
                .selectinload(db_models.FeedbackPoint.focus_goal),
                selectinload(db_models.Session.jobs),
            )
        )
        # Before the slice, and on the filtered query: the client needs to know
        # whether more pages exist, which the page itself cannot say.
        total = query.order_by(None).count()
        sessions = (
            # session_id breaks a tie on the timestamp. Two Sessions can share
            # a started_at -- it comes from the client's `session.activate` --
            # and an order Postgres is free to choose would put them in a
            # different sequence on each read, which paginates badly: a row can
            # appear on two pages or on none.
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
            "sessions": [_session_summary(s) for s in sessions],
        }


def _session_summary(session: db_models.Session) -> dict:
    """One row of the history. `status` is `session.status` here -- completed
    or aborted (ADR 0057) -- not the feedback status the detail route reports
    under the same key; that one is `feedback_status`.

    Both wrap-up fields are present because they answer different questions.
    `has_feedback` is "is there something to open", which is what the row's
    link is worth; `feedback_status` is why not, which is what distinguishes a
    wrap-up still being generated from one that will never arrive. Deriving
    either from the other would be a guess: a job reading `done` whose feedback
    row is missing is exactly the case the reader must not paper over.
    """
    return {
        "session_id": str(session.extern_id),
        "persona": session.persona.name,
        "scenario": session.scenario.title,
        # Whether this training was a reverse (ADR 0070), so the history can
        # say so on the row. The Scenario is already loaded for its title.
        "reverse": session.scenario.reverse,
        "status": session.status,
        "has_feedback": session.feedback is not None,
        "feedback_status": _feedback_status(session),
        # The wrap-up's tagged points: kind, focus-goal key and the sentence
        # itself. Enough for the dashboard to say "the closing came up as an
        # improvement in 4 of your last 8 wrap-ups" *and* to show what was
        # written each time, which is what its second level asks for.
        #
        # Here and not on an aggregate route of its own, for the reason the
        # progress view adds no endpoint at all: a second path to the same
        # numbers is a second place for them to drift. The summary and the
        # untagged points stay on the detail route -- this carries what can be
        # counted, not the wrap-up.
        "feedback_goals": _feedback_goals(session.feedback),
        # Explicit isoformat rather than leaving it to the serializer: the wire
        # format is part of what the frontend parses, not an incidental
        # property of how this dict happens to be encoded.
        "started_at": session.started_at.isoformat(),
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "measurements": [
            {
                "key": m.metric_type.key,
                "name": m.metric_type.name,
                "unit": m.metric_type.unit,
                # Which half of the metrics the metric belongs to (ADR 0064's
                # `aspect`). The detail route has carried it since the post-call
                # screen split its grid in two; the dashboard needs the same
                # split, and a copy of the mapping in the frontend would drift
                # from the column the moment a metric is added.
                "aspect": m.metric_type.aspect,
                "value": float(m.value),
                # Whether this metric is still part of the current inventory
                # (`backend/feedback/metrics.py`). A Session measured before a
                # metric was renamed keeps pointing at the retired row, and
                # nothing else on the wire would let a caller tell the two
                # apart: both carry the same display name. The progress view
                # (F-13) needs to, or one renamed metric becomes two identical
                # cards. The detail route deliberately does not filter -- a past
                # Session shows what was measured then.
                "active": m.metric_type.active,
            }
            for m in session.measurements
            # Whole-call rows only. `toSeries` builds one series per metric key
            # and would splice the pressure figure of one training into the
            # same line as the whole-call figure of the next.
            if m.segment == db_models.SEGMENT_CALL
        ],
        # The demanding stretches against the rest (ADR 0081), which is the
        # only data behind the focus goal "composure under pressure" and
        # therefore has to reach the dashboard rather than stopping at the
        # single call. Figures only, never their curves.
        "segments": _segments(session),
    }


@router.get("/{extern_id}")
def get_session(extern_id: uuid.UUID, caller: AuthContext = Depends(require_user)) -> dict:
    """One finished Session: Transcript, measurements, Feedback."""
    with session_scope() as db:
        session = (
            db.query(db_models.Session)
            .filter_by(extern_id=extern_id)
            .options(
                *SESSION_SUBTREE,
                selectinload(db_models.Session.jobs),
                selectinload(db_models.Session.findings),
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
            # The id alongside the name: the follow-up offered below starts the
            # next call against the same partner, and `session.start` takes the
            # `extern_id` (ADR 0050), never a display name.
            "persona_id": str(session.persona.extern_id),
            "scenario": session.scenario.title,
            "reverse": session.scenario.reverse,
            "status": _feedback_status(session),
            "turns": [_turn(t) for t in sorted(session.turns, key=lambda t: t.seq_index)],
            # The whole call's figures, and only those. The segment rows travel
            # under their own key rather than in this list: every reader of it
            # assumes one entry per metric (ADR 0051), and mixing three
            # speaking pace rows in would draw the metric three times.
            "measurements": [
                _measurement(m) for m in session.measurements
                if m.segment == db_models.SEGMENT_CALL
            ],
            # The same metrics over the demanding stretches and over the
            # rest (ADR 0081). Empty where nobody pushed back, where the
            # stretches were too short to measure, and for every call recorded
            # before the per-utterance facts were kept.
            "segments": _segments(session),
            # Individual moments that were noted, ordered as they happened. The
            # counterpart to a Measurement: a Measurement is what the whole call
            # amounted to, a Finding is one thing that occurred at one point
            # (F-51 writes the first of them). Sorted here so the client does
            # not have to know that they belong on the transcript's timeline.
            "findings": [
                _finding(f) for f in sorted(session.findings, key=lambda f: f.offset_ms or 0)
            ],
            # The long explanation behind a metric's "i", by metric key.
            # Read from the Python constant at request time rather than stored
            # with the Session or copied into the frontend: it explains the
            # thresholds it sits next to, and the two have to be edited
            # together (the arrangement ADR 0063 chose for the field limits).
            "metric_notes": {
                interruptions.COUNT_KEY: interruptions.EXPLANATION,
                intonation.RANGE_KEY: intonation.EXPLANATION,
                metrics.RUN_LENGTH_KEY: metrics.RUN_LENGTH_EXPLANATION,
            },
            # The scales those readings come from, written out. A boundary the
            # user cannot see is a judgement they cannot argue with, and both
            # sets of boundaries are working values (see the two modules).
            "metric_scales": {
                interruptions.COUNT_KEY: interruptions.light_steps(),
                intonation.RANGE_KEY: intonation.liveliness_steps(),
            },
            "feedback": _feedback(session.feedback),
            "follow_up": _follow_up(db, session.session_id),
        }


@router.delete("/{extern_id}", status_code=204, response_class=Response)
def delete_one_session(
    extern_id: uuid.UUID, caller: AuthContext = Depends(require_user)
) -> Response:
    """Delete one of the caller's own stored trainings (ADR 0066).

    204 on success, 404 for an id that does not exist *or* is not the caller's
    — the same answer the read route gives, for the same reason (ADR 0050): a
    distinct response would confirm that an id exists, which is what makes it
    worth guessing at.

    Not idempotent in the HTTP sense on purpose: a second DELETE of the same id
    is a 404, because by then it is indistinguishable from a wrong id. The
    underlying operation is idempotent — nothing breaks — but the route will
    not claim a training was deleted twice.
    """
    with session_scope() as db:
        if not deletion.delete_session(db, caller.sub, extern_id):
            raise HTTPException(status_code=404, detail="Unknown session")
    # Returned explicitly rather than annotated `-> None`: FastAPI derives a
    # response model from the annotation, and a 204 may not carry a body.
    return Response(status_code=204)


@router.post("/{extern_id}/reverse")
async def create_reverse(
    extern_id: uuid.UUID,
    caller: AuthContext = Depends(require_user),
    tenant_id: int = Depends(current_tenant_id),
) -> dict:
    """The reverse of this Session: the same call with the roles swapped (F-61).

    Like the follow-up (ADR 0069) it writes a Scenario the User owns, so both
    end up in the same library; unlike it, this one is asked for rather than
    written by the worker, because a reverse is a thing you decide to do about
    a call you have just had.

    Idempotent, and cheaply so: the existing reverse is looked up before any
    model call, so pressing the button twice costs nothing and yields the same
    row. A reverse of a reverse is refused: the roles are already swapped, and
    swapping them again is the original call with a copied briefing.

    No consent guard, and none is needed (ADR 0066): without consent no Session
    is written, and without a stored Session there is nothing here to read — the
    first lookup answers 404. A withdrawal mid-flight removes the Session, so
    the write below then finds nothing and answers the same way.

    `session_scope()` is synchronous, so every read and write goes to a thread
    — this route is `async def` for the model call and must not block the loop.
    """
    material = await asyncio.to_thread(_reverse_material, extern_id, caller.sub)
    # Absent and not-yours stay the same answer as in `get_session` (ADR 0050).
    if material is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    if material.already_reverse:
        raise HTTPException(
            status_code=409,
            detail="Dieses Gespräch ist selbst schon ein Rollentausch.",
        )
    if not material.has_turns:
        raise HTTPException(
            status_code=409,
            detail="Zu diesem Gespräch wurde nichts gesprochen, was sich tauschen ließe.",
        )

    existing = await asyncio.to_thread(library.restore_reverse, material.session_pk)
    if existing is not None:
        return _reverse_response(existing)

    try:
        brief = await draft_brief(
            material.description,
            material.case_facts,
            material.call_goal,
            material.improvements,
        )
    except (OpenAIError, ReverseError) as e:
        # A dead gateway and an unparseable reply are the same thing from here.
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
        # The Session went away between the two reads — a deletion in another
        # tab. Nothing was written; the same 404 the first read would have given.
        raise HTTPException(status_code=404, detail="Unknown session")
    return _reverse_response(scenario)


def _reverse_response(scenario) -> dict:
    """What the client needs to start the reverse straight away: the id to
    commit a Session with, and the briefing to show while it runs."""
    return {
        "id": scenario.id,
        "name": scenario.name,
        "short_description": scenario.short_description,
        "reverse_brief": scenario.reverse_brief,
    }


@dataclass(frozen=True)
class _ReverseMaterial:
    """What a reverse is built from, read out before the database handle is
    gone. The played Scenario's prompt fields are in here on purpose: the
    briefing is a translation of exactly those, which is the exception ADR 0070
    takes to ADR 0043 and the reason it is only ever taken for a case the User
    has already heard played out."""

    session_pk: int
    already_reverse: bool
    has_turns: bool
    description: str
    case_facts: str
    call_goal: str
    improvements: list[str]


def _reverse_material(extern_id: uuid.UUID, subject: str) -> _ReverseMaterial | None:
    """This Session's material, or None if it is not the caller's."""
    with session_scope() as db:
        session = (
            db.query(db_models.Session)
            .filter_by(extern_id=extern_id)
            .options(
                selectinload(db_models.Session.scenario),
                selectinload(db_models.Session.turns),
                selectinload(db_models.Session.feedback)
                .selectinload(db_models.Feedback.points),
            )
            .one_or_none()
        )
        if session is None or session.subject_id != subject:
            return None
        scenario = session.scenario
        feedback = session.feedback
        return _ReverseMaterial(
            session_pk=session.session_id,
            already_reverse=scenario.reverse,
            has_turns=bool(session.turns),
            description=scenario.description,
            case_facts=scenario.case_facts,
            call_goal=scenario.call_goal,
            # Absent when the wrap-up has not landed, which is allowed here:
            # the briefing is built from the case, and the coaching points only
            # decide which goal the checklist names first.
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
    """The next exercise, drafted from this Session's wrap-up (F-60).

    The sibling of the reverse below it, deliberately down to the shape: same
    refusals, same idempotency, same 503. It was once written by the Feedback
    worker without anyone asking — ADR 0069's amendment says why that changed,
    and the short of it is that a library filling itself with exercises nobody
    chose is a library people stop reading.

    409 rather than 404 when the wrap-up names nothing to work on: the Session
    is the caller's and does exist, and the improvement points are what makes
    the next call an exercise — without them it would only carry the case
    forward, with nothing to practise. The client hides the button in that
    case, so this is the second line of defence, not the message anyone
    should normally see.

    `session_scope()` is synchronous, so every read and write goes to a thread
    — this route is `async def` for the model call and must not block the loop.
    """
    material = await asyncio.to_thread(_follow_up_material, extern_id, caller.sub)
    # Absent and not-yours stay the same answer as in `get_session` (ADR 0050).
    if material is None:
        raise HTTPException(status_code=404, detail="Unknown session")
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

    try:
        draft = await draft_follow_up(material.call)
    except (OpenAIError, FollowUpError) as e:
        # A dead gateway and an unusable draft are the same thing from here.
        logger.warning("Follow-up draft failed for session %s: %s", extern_id, e)
        raise HTTPException(
            status_code=503,
            detail=(
                "Das Folgeszenario konnte gerade nicht erstellt werden. "
                "Bitte später noch einmal versuchen."
            ),
        ) from e

    # The draft is keyed as the client knows the fields (ADR 0061); the library
    # writes columns, where the card's `name` is `title`.
    draft["title"] = draft.pop("name")
    scenario = await asyncio.to_thread(
        library.create_follow_up, draft, caller.sub, tenant_id, material.session_pk
    )
    if scenario is None:
        # The Session went away between the two reads — a deletion in another
        # tab. The same 404 the first read would have given.
        raise HTTPException(status_code=404, detail="Unknown session")
    return _follow_up_response(scenario)


def _follow_up_response(scenario) -> dict:
    """The card, in the shape `_follow_up` below already hands the client on the
    detail route — so the screen renders what it came back with and what a
    later reload brings identically."""
    return {
        "id": scenario.id,
        "name": scenario.name,
        "short_description": scenario.short_description,
    }


@dataclass(frozen=True)
class _FollowUpMaterial:
    """What a follow-up is drafted from, read out before the database handle is
    gone. The played Scenario's prompt fields are in here, exactly as they are
    for the reverse above: a follow-up carries that case forward, and ADR 0070
    already takes this exception to ADR 0043 for a case the User has just heard
    played out. The measured statistics stay out -- no target range exists to
    correct a figure against (ADR 0051)."""

    session_pk: int
    call: PlayedCall


def _follow_up_material(extern_id: uuid.UUID, subject: str) -> _FollowUpMaterial | None:
    """This Session's material, or None if it is not the caller's.

    A Session whose wrap-up never landed comes back with no improvements, which
    the route refuses the same way it refuses a wrap-up that named none: from
    here the two are one case, because the input is missing either way.
    """
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
        scenario = session.scenario
        feedback = session.feedback
        return _FollowUpMaterial(
            session_pk=session.session_id,
            call=PlayedCall(
                scenario_name=scenario.title,
                scenario_teaser=scenario.short_description,
                description=scenario.description,
                case_facts=scenario.case_facts,
                call_goal=scenario.call_goal,
                # Where the call ended up, in the wrap-up's own words. The next
                # call starts from that, and no other field says it.
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
    """The card of the Scenario drafted from this Session (ADR 0069), or None.

    Its own query rather than a relationship: `scenario` and `session` already
    point at each other through `session.scenario_id`, and a second mapped edge
    between them would have to disambiguate the first one everywhere.

    Filtered on `active`, so a follow-up the User has since deleted stops being
    offered — which is also what a deleted source Session leaves behind.
    """
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


def _feedback_goals(feedback: db_models.Feedback | None) -> list[dict[str, str]]:
    """The focus goals this wrap-up's points were assigned to, with their kind
    and the point itself.

    Untagged points are left out rather than sent with a null goal. They cannot
    be counted, so a caller would have to filter them anyway, and a row of
    nulls invites somebody to treat "not assigned" as a category of its own.

    Order follows `feedback.points`, which is `position`, so a caller that
    wants the most prominent point of a kind can take the first. Duplicates are
    kept: two improvements about the closing in one call are two points, and
    collapsing them here would decide something the reader should.

    `text` rides along since the progress view's second level, which has to say
    what the wrap-ups actually wrote about a goal and not only how often they
    wrote it (docs/dashboard-konzept.md, section 7). ADR 0064's amendment has
    the reasoning: what that decision keeps off the listing is `detail_json`,
    a curve per metric per Session, and a tagged point is two sentences.
    """
    if feedback is None:
        return []
    return [
        {"kind": point.kind, "goal": point.focus_goal.key, "text": point.text}
        for point in feedback.points
        if point.focus_goal is not None
    ]


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
        # Both only ever set on a Persona line the user cut into (F-51). The
        # unheard part is what the Persona had been about to say; it is not part
        # of the transcript and must never be rendered as though it were.
        "interrupted": turn.interrupted,
        "unheard_text": turn.unheard_text,
    }


def _finding(finding: db_models.Finding) -> dict:
    """One noted moment. `category` is the machine-readable kind (the interface
    decides how to word it), `offset_ms` places it on the transcript's timeline,
    `description` is the sentence already written for the user."""
    return {
        "category": finding.category,
        "offset_ms": finding.offset_ms,
        "description": finding.description,
        # Which figure this moment belongs to, so the interface can show it
        # beside the right metric. NULL for a Finding that stands alone.
        "metric_key": finding.metric_type.key if finding.metric_type else None,
    }


def _segments(session: db_models.Session) -> list[dict]:
    """The per-segment figures of one Session (ADR 0081), whole-call rows left
    out because they are the list beside this one.

    No `detail`, for ADR 0064's reason one level down: the loudness curve of a
    segment is a curve like any other, nothing plots it, and it would outweigh
    everything else here. The figure and which stretch it describes is the
    whole of what the comparison needs.

    Ordered by metric and then segment, so the two halves of a comparison
    arrive next to each other however the database happened to return them.
    """
    return [
        {
            "segment": m.segment,
            "key": m.metric_type.key,
            "name": m.metric_type.name,
            "unit": m.metric_type.unit,
            "value": float(m.value),
        }
        for m in sorted(
            (m for m in session.measurements if m.segment != db_models.SEGMENT_CALL),
            key=lambda m: (m.metric_type.key, m.segment),
        )
    ]


def _measurement(measurement: db_models.Measurement) -> dict:
    key = measurement.metric_type.key
    value = float(measurement.value)
    return {
        "key": key,
        "name": measurement.metric_type.name,
        "unit": measurement.metric_type.unit,
        # Which half of the metrics grid this one sits in; display only.
        "aspect": measurement.metric_type.aspect,
        "value": value,
        "detail": _served_detail(key, measurement.detail_json),
    }


def _served_detail(key: str, detail: dict | None) -> dict | None:
    """The stored facts, plus the reading derived from them at request time.

    The split is the point. What the analysis measured is written once and kept
    (ADR 0051); which step of a scale that lands on is a judgement resting on
    thresholds nothing has validated yet, so it is computed here, on every read,
    from the stored figures. A recalibration then reaches every Session that was
    ever measured -- including the ones whose audio is long gone (ADR 0048) --
    instead of leaving old trainings labelled by a scale that no longer exists.
    That has now happened once: F-35's reading moved from the range onto the
    pitch variation quotient, and every stored Session picked up the new scale
    on the next read, or lost its step where the new input was never measured.

    F-51's traffic light predates this and is still stored in its detail; only
    its wording is added here, so the German lives beside the thresholds.
    """
    if detail is None:
        return None
    if key == intonation.RANGE_KEY:
        # Off the pitch variation quotient in the detail, not off `value`, which
        # is the range. The two are different figures and only one of them has
        # a boundary anybody has published -- see `intonation.liveliness`. A
        # Session measured before the quotient was computed carries no `pvq` and
        # gets no step, which is the honest answer rather than a gap.
        step = intonation.liveliness(detail.get("pvq"), detail.get("voiced_ms"))
        if step is None:
            return detail  # not measured, or on too little speech to be read
        return {
            **detail,
            "liveliness": step.value,
            "liveliness_label": intonation.LABELS[step],
            # The colour travels with the word, from beside the threshold that
            # decided both. The frontend maps no step to any colour of its own.
            "liveliness_light": intonation.LIGHTS[step],
        }
    if key == interruptions.COUNT_KEY:
        try:
            light = interruptions.TrafficLight(detail.get("light"))
        except ValueError:
            return detail  # measured before the light existed, or a value since retired
        return {**detail, "light_label": interruptions.LABELS[light]}
    return detail


def _feedback(feedback: db_models.Feedback | None) -> dict | None:
    if feedback is None:
        return None
    return {
        "summary": feedback.summary,
        # NULL where the wrap-up carries no phase analysis (F-42) -- an older
        # Session, or one whose model answer fell back to narrative only. The
        # frontend drops the block rather than showing an empty one.
        "phase_language": feedback.phase_language,
        # NULL on the same grounds: a Session whose wrap-up predates the block,
        # or one the model left it out of. The block is omitted, not emptied.
        "tone_fit": feedback.tone_fit,
        "points": [
            {
                "kind": p.kind,
                "text": p.text,
                "turn_id": p.turn_id,
                # The focus goal this point was assigned to, or null where the
                # wrap-up predates the tag or nothing in the catalogue fitted.
                "goal": p.focus_goal.key if p.focus_goal else None,
            }
            for p in feedback.points
        ],
    }
