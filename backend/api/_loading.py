"""How a route loads a Session: whose it may be, and what comes with it.

Shared so the eager-load lists cannot drift apart (a missing relationship is
not an error, just one query per row), and so ownership is a filter in the
query rather than a comparison afterwards that one path could forget."""

import uuid

from sqlalchemy.orm import Session as DbSession, selectinload
from sqlalchemy.orm.interfaces import LoaderOption

from backend.db import models as db_models

#: What every Session-serving route needs. The two callers differ only in what
#: they add to it -- the detail route also reads the analysis jobs and the
#: Findings, which the export has no place for.
SESSION_SUBTREE = (
    selectinload(db_models.Session.turns),
    selectinload(db_models.Session.measurements)
    .selectinload(db_models.Measurement.metric_type),
    # Down to the focus goal: `served._detail_feedback` reads
    # `point.focus_goal.key`, a lazy relationship, so without this a wrap-up
    # costs a query per tagged point. The listing route carries the same load.
    selectinload(db_models.Session.feedback)
    .selectinload(db_models.Feedback.points)
    .selectinload(db_models.FeedbackPoint.focus_goal),
    selectinload(db_models.Session.persona),
    selectinload(db_models.Session.scenario),
)

#: What the two routes that build a Scenario from a Session read (ADR 0100):
#: the case that was played and the wrap-up's points.
WITH_WRAPUP = (
    selectinload(db_models.Session.scenario),
    selectinload(db_models.Session.feedback).selectinload(db_models.Feedback.points),
)

#: Exactly what `jobs.retry_blocked` walks: the wrap-up, the Turns and the jobs.
#: The Turns load in full to answer `not session.turns`; an EXISTS would be
#: cheaper, but the rule also serves `requeue_feedback.py` and a transcript is
#: tens of rows.
FOR_RETRY = (
    selectinload(db_models.Session.feedback),
    selectinload(db_models.Session.turns),
    selectinload(db_models.Session.jobs),
)


def owned_session(
    db: DbSession, subject: str, extern_id: uuid.UUID, *loads: LoaderOption
) -> db_models.Session | None:
    """The caller's Session with `extern_id`, or None.

    None both for an absent id and for someone else's: telling them apart
    would confirm the id exists (ADR 0031/0050).
    """
    return (
        db.query(db_models.Session)
        .filter_by(extern_id=extern_id, subject_id=subject)
        .options(*loads)
        .one_or_none()
    )
