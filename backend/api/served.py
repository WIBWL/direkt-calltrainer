"""A stored Session as it goes out on the wire -- the listing's row, the detail
route's whole Session, and the subject's export.

Three shapes, and they are deliberately three: the listing drops
`detail_json` and the wrap-up text (ADR 0064), the detail route serves the
Reading beside each figure (ADR 0091), the export carries every row the
subject owns (ADR 0066). What they share is here once -- how a metric is
named, how Turns and Findings are ordered, which rows are the whole call and
what the wrap-up's state is -- so a field added to one of those reaches every
route that serves it, instead of three edits of which nothing fails when one
is forgotten.

Plain functions over loaded ORM rows. The routes load (and decide what to
eager-load, `_loading.py`), check ownership and answer; nothing here queries,
which is also what makes the wire shape testable without a database.

The two `_feedback` shapes stay two: the export serves `created_at` and plain
points, the detail route `turn_id` and the focus goal. Merging them would need
a flag, and a serializer with a flag is worse than two honest ones.

The wire matches the schema (ADR 0057): the ORM's own English column values
pass straight through to frontend/src/protocol.ts, with no translation step.
"""

from __future__ import annotations

from backend.db import models as db_models
from backend.feedback import readings, stored
from backend.feedback.jobs import is_live


def _metric(metric_type: db_models.MetricType) -> dict:
    """What names a figure, on every route that serves one."""
    return {"key": metric_type.key, "name": metric_type.name, "unit": metric_type.unit}


def _findings(session: db_models.Session) -> list[db_models.Finding]:
    """Ordered as they happened: they belong on the transcript's timeline, and
    the client should not have to know that."""
    return sorted(session.findings, key=lambda f: f.offset_ms or 0)


def summary(session: db_models.Session) -> dict:
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
        # The kind of call this was (ADR 0072's vocabulary), so the dashboard
        # can read a course over one kind rather than over everything.
        #
        # It answers the concept's own objection to its charts: Scenario and
        # Persona move talk share, pace and question count more than a change
        # in behaviour does, so a line across every training shows scatter
        # where it looks like development. Nullable, as the column is, and the
        # frontend treats an uncategorised training as its own bucket rather
        # than dropping it.
        "category": session.scenario.category,
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
                **_metric(m.metric_type),
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
            # Whole-call rows only. `toSeries` builds one series per metric key
            # and would splice the pressure figure of one training into the
            # same line as the whole-call figure of the next.
            for m in stored.whole_call(session)
        ],
        # The demanding stretches against the rest (ADR 0081), which is the
        # only data behind the focus goal "composure under pressure" and
        # therefore has to reach the dashboard rather than stopping at the
        # single call. Figures only, never their curves.
        "segments": _segments(session),
    }


def detail(session: db_models.Session, *, follow_up: dict | None) -> dict:
    """One finished Session: Transcript, measurements, Feedback.

    `follow_up` is the card of the Scenario drafted from it (ADR 0069), looked
    up by the route, since it is a query and this module runs none.
    """
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
        "turns": [_turn(t) for t in stored.ordered_turns(session)],
        # The whole call's figures, and only those. The segment rows travel
        # under their own key rather than in this list: every reader of it
        # assumes one entry per metric (ADR 0051), and mixing three
        # speaking pace rows in would draw the metric three times.
        "measurements": [_measurement(m) for m in stored.whole_call(session)],
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
        "findings": [_finding(f) for f in _findings(session)],
        # What each metric says beyond its figure -- the text behind its
        # "i", and the scale a coloured step was read off. Which metrics
        # have either is `backend/feedback/readings.py`'s business and not
        # this route's: a list of metric keys in an HTTP module is one a
        # new metric is silently missing from.
        "metric_notes": readings.notes(),
        "metric_scales": readings.scales(),
        "feedback": _detail_feedback(session.feedback),
        "follow_up": follow_up,
    }


def export(session: db_models.Session) -> dict:
    """One Session in the subject's own copy of their data (ADR 0066).

    Everything the Session owns, `detail_json` and every segment row included:
    completeness outweighs payload size here, which is the opposite trade from
    the listing's."""
    return {
        "session_id": str(session.extern_id),
        "persona": session.persona.name,
        "scenario": session.scenario.title,
        "language": session.language_code,
        "status": session.status,
        "started_at": session.started_at.isoformat(),
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "transcript": [
            {
                "speaker": t.speaker,
                "start_offset_ms": t.start_offset_ms,
                "duration_ms": t.duration_ms,
                "text": t.transcript,
            }
            for t in stored.ordered_turns(session)
        ],
        "measurements": [
            {
                **_metric(m.metric_type),
                "value": float(m.value),
                # Which stretch of the call this figure describes (ADR 0081).
                # Without it the three rows a metric can have -- whole call,
                # under pressure, the rest -- arrive as three identical keys
                # with different numbers and nothing to tell them apart.
                "segment": m.segment,
                # Included here although the listing drops it (ADR 0064): this
                # is the subject's own copy of their data, so completeness
                # outweighs payload size, which is the opposite trade.
                "detail": m.detail_json,
            }
            for m in session.measurements
        ],
        # One row per event that occurred in the call (F-51), not a judgement
        # against a threshold -- and stored against this Session, so the
        # subject's copy has to carry them.
        "findings": [
            {
                "category": f.category,
                "offset_ms": f.offset_ms,
                "description": f.description,
            }
            for f in _findings(session)
        ],
        "feedback": _export_feedback(session.feedback),
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
    wrote it (docs/dashboard-concept.md, section 7). ADR 0064's amendment has
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

    Read as failed rather than left spinning; the row itself is not touched,
    because this is the reader's judgement and not a repair. A *queued* row is
    not abandoned, it is waiting, which is why the question is asked without
    it -- `jobs.is_live` owns the window and both answers.
    """
    return job.status == db_models.JOB_RUNNING and not is_live(job, include_queued=False)


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
            **_metric(m.metric_type),
            "value": float(m.value),
        }
        for m in sorted(
            (m for m in session.measurements if m.segment != db_models.SEGMENT_CALL),
            key=lambda m: (m.metric_type.key, m.segment),
        )
    ]


def _measurement(measurement: db_models.Measurement) -> dict:
    return {
        **_metric(measurement.metric_type),
        # Which half of the metrics grid this one sits in; display only.
        "aspect": measurement.metric_type.aspect,
        "value": float(measurement.value),
        "detail": readings.served_detail(measurement.metric_type.key, measurement.detail_json),
    }


def _detail_feedback(feedback: db_models.Feedback | None) -> dict | None:
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


def _export_feedback(feedback: db_models.Feedback | None) -> dict | None:
    if feedback is None:
        return None
    return {
        "summary": feedback.summary,
        "phase_language": feedback.phase_language,
        "tone_fit": feedback.tone_fit,
        "created_at": feedback.created_at.isoformat(),
        "points": [
            {"kind": p.kind, "text": p.text} for p in feedback.points
        ],
    }
