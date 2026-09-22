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
    selectinload(db_models.Session.feedback)
    .selectinload(db_models.Feedback.points),
    selectinload(db_models.Session.persona),
    selectinload(db_models.Session.scenario),
)

#: What the two routes that build a Scenario from a Session read (ADR 0100):
#: the case that was played and the wrap-up's points.
WITH_WRAPUP = (
    selectinload(db_models.Session.scenario),
    selectinload(db_models.Session.feedback).selectinload(db_models.Feedback.points),
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
