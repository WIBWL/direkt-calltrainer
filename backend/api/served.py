"""A stored Session's three wire shapes: history row (ADR 0064), detail (ADR 0091)
and export (ADR 0066). Pure functions over loaded rows; they never query."""

from __future__ import annotations

from shared.db import models as db_models
from shared.feedback import stored
from shared.feedback.jobs import is_live
from backend.feedback import readings


def _metric(metric_type: db_models.MetricType) -> dict:
    return {"key": metric_type.key, "name": metric_type.name, "unit": metric_type.unit}


def _findings(session: db_models.Session) -> list[db_models.Finding]:
    return sorted(session.findings, key=lambda f: f.offset_ms or 0)


def summary(session: db_models.Session) -> dict:
    """`status` is the Session's outcome here, not the job status. `has_feedback`
    and `feedback_status` are never derived from each other."""
    return {
        "session_id": str(session.extern_id),
        "persona": session.persona.name,
        "scenario": session.scenario.title,
        "reverse": session.scenario.reverse,
        # The kind of call, for courses over one kind (ADR 0072).
        "category": session.scenario.category,
        "status": session.status,
        "has_feedback": session.feedback is not None,
        "feedback_status": _feedback_status(session),
        # Tagged points the progress view counts and quotes (ADR 0064).
        "feedback_goals": _feedback_goals(session.feedback),
        "started_at": session.started_at.isoformat(),
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "measurements": [
            {
                **_metric(m.metric_type),
                "aspect": m.metric_type.aspect,
                "value": float(m.value),
            }
            # Whole-call rows only, or a series would splice in segment figures.
            for m in stored.whole_call(session)
        ],
        # The only data behind "composure under pressure" (ADR 0081); figures only.
        "segments": _segments(session),
    }


def detail(session: db_models.Session, *, follow_up: dict | None) -> dict:
    """`follow_up` is looked up by the route, since this module runs no queries."""
    return {
        "session_id": str(session.extern_id),
        "persona": session.persona.name,
        # `session.start` takes the id, never a display name.
        "persona_id": str(session.persona.extern_id),
        "scenario": session.scenario.title,
        "reverse": session.scenario.reverse,
        "status": _feedback_status(session),
        "turns": [_turn(t) for t in stored.ordered_turns(session)],
        # Whole-call only; readers assume one entry per metric.
        "measurements": [_measurement(m) for m in stored.whole_call(session)],
        "segments": _segments(session),
        "findings": [_finding(f) for f in _findings(session)],
        # Which metrics carry notes or scales is readings.py's business.
        "metric_notes": readings.notes(),
        "metric_scales": readings.scales(),
        "feedback": _detail_feedback(session.feedback),
        "follow_up": follow_up,
    }


def export(session: db_models.Session) -> dict:
    """Everything the Session owns, `detail_json` included: completeness over size."""
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
                # Tells apart the up to three rows a metric can have.
                "segment": m.segment,
                "detail": m.detail_json,
            }
            for m in session.measurements
        ],
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
    """Untagged points are left out."""
    if feedback is None:
        return []
    return [
        {"kind": point.kind, "goal": point.focus_goal.key, "text": point.text}
        for point in feedback.points
        if point.focus_goal is not None
    ]


def _feedback_status(session: db_models.Session) -> str:
    """No job row means nothing will ever generate a wrap-up: "failed"."""
    jobs = [j for j in session.jobs if j.kind == db_models.JOB_KIND_FEEDBACK]
    if not jobs:
        return db_models.JOB_FAILED
    job = max(jobs, key=lambda j: j.job_id)
    return db_models.JOB_FAILED if _abandoned(job) else job.status


def _abandoned(job: db_models.AnalysisJob) -> bool:
    """A `running` row older than a job may run reads as failed; it is not repaired."""
    return job.status == db_models.JOB_RUNNING and not is_live(job, include_queued=False)


def _turn(turn: db_models.Turn) -> dict:
    return {
        "turn_id": turn.turn_id,
        "speaker": turn.speaker,
        "start_offset_ms": turn.start_offset_ms,
        "duration_ms": turn.duration_ms,
        "transcript": turn.transcript,
        # The unheard part must never be rendered as transcript.
        "interrupted": turn.interrupted,
        "unheard_text": turn.unheard_text,
    }


def _finding(finding: db_models.Finding) -> dict:
    return {
        "category": finding.category,
        "offset_ms": finding.offset_ms,
        "description": finding.description,
        "metric_key": finding.metric_type.key if finding.metric_type else None,
    }


def _segments(session: db_models.Session) -> list[dict]:
    """Ordered so the two halves of a comparison arrive side by side; no `detail`."""
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
        "aspect": measurement.metric_type.aspect,
        "value": float(measurement.value),
        "detail": readings.served_detail(measurement.metric_type.key, measurement.detail_json),
    }


def _detail_feedback(feedback: db_models.Feedback | None) -> dict | None:
    if feedback is None:
        return None
    return {
        "summary": feedback.summary,
        # NULL when the model omitted it; the frontend drops the block.
        "phase_language": feedback.phase_language,
        "tone_fit": feedback.tone_fit,
        "points": [
            {
                "kind": p.kind,
                "text": p.text,
                "turn_id": p.turn_id,
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
