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

The detail route also carries the follow-up Scenario the worker drafted from
this Session's Feedback (F-60, ADR 0069) — its card, which is what the post-call
screen offers to start or to edit.

The wire matches the schema (ADR 0057): the dicts below pass the ORM's own
English column values straight through to frontend/src/protocol.ts, with no
translation step.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session as DbSession, selectinload

from backend import deletion
from backend.auth import AuthContext, require_user
from backend.db import models as db_models
from backend.db.session import session_scope
from backend.feedback import interruptions

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
                selectinload(db_models.Session.feedback),
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
        "status": session.status,
        "has_feedback": session.feedback is not None,
        "feedback_status": _feedback_status(session),
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
        ],
    }


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
            "status": _feedback_status(session),
            "turns": [_turn(t) for t in sorted(session.turns, key=lambda t: t.seq_index)],
            "measurements": [_measurement(m) for m in session.measurements],
            # Individual moments that were noted, ordered as they happened. The
            # counterpart to a Measurement: a Measurement is what the whole call
            # amounted to, a Finding is one thing that occurred at one point
            # (F-51 writes the first of them). Sorted here so the client does
            # not have to know that they belong on the transcript's timeline.
            "findings": [
                _finding(f) for f in sorted(session.findings, key=lambda f: f.offset_ms or 0)
            ],
            # The long explanation behind a Kennzahl's "i", by metric key.
            # Read from the Python constant at request time rather than stored
            # with the Session or copied into the frontend: it explains the
            # thresholds it sits next to, and the two have to be edited
            # together (the arrangement ADR 0063 chose for the field limits).
            "metric_notes": {interruptions.COUNT_KEY: interruptions.EXPLANATION},
            # The scale the traffic light comes from, written out. A boundary
            # the user cannot see is a judgement they cannot argue with, and
            # these boundaries are working values (see `interruptions.py`).
            "metric_scales": {interruptions.COUNT_KEY: interruptions.light_steps()},
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
        # beside the right Kennzahl. NULL for a Finding that stands alone.
        "metric_key": finding.metric_type.key if finding.metric_type else None,
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
