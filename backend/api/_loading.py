"""How a route loads a Session: whose it may be, and what comes with it.

Both the detail route and the data export read a Session with its whole subtree,
and both had their own copy of the list. The risk is not the duplication itself
but the drift: a relationship added to one and not the other is not an error,
it is the same page served with one query per row.

`owned_session` is the same argument for the ownership rule. Every route that
reads one Session by its `extern_id` wrote the query itself, and one of them
loaded the row and compared the owner afterwards -- the shape `deletion.py`
calls unsafe, since a comparison can be forgotten on one path the way a filter
in the query cannot.
"""

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
    # Down to the focus goal, not only to the points: `served._detail_feedback`
    # reads `point.focus_goal.key` for every point, and that relationship is a
    # plain lazy one, so without this a wrap-up costs a query per tagged point.
    # The listing route carries the same load for the same reason -- it is the
    # one place this was noticed, and having it there and not here is exactly
    # the drift this module exists to prevent. The export pays one batched
    # query it does not read, which is a query, not a query per point.
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

#: Exactly what `jobs.retry_blocked` walks, and nothing else: the wrap-up it
#: refuses a second one for, the Turns it needs at least one of, and the jobs
#: whose newest it reads. The route asked without any of them and paid three
#: lazy loads for a single decision.
#:
#: The Turns come back in full to answer `not session.turns`. An EXISTS would
#: be cheaper, but the same function serves `requeue_feedback.py`, and a
#: transcript is tens of rows -- not worth splitting one rule into two shapes.
FOR_RETRY = (
    selectinload(db_models.Session.feedback),
    selectinload(db_models.Session.turns),
    selectinload(db_models.Session.jobs),
)


def owned_session(
    db: DbSession, subject: str, extern_id: uuid.UUID, *loads: LoaderOption
) -> db_models.Session | None:
    """The caller's Session with `extern_id`, or None.

    None for one that is absent *and* for one that is someone else's: the two
    are the same answer (ADR 0031/0050), because telling them apart would
    confirm that an id exists. The owner is part of the query, so someone
    else's row and its subtree are never loaded only to be thrown away.
    """
    return (
        db.query(db_models.Session)
        .filter_by(extern_id=extern_id, subject_id=subject)
        .options(*loads)
        .one_or_none()
    )
