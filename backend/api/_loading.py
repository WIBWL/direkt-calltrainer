"""Eager-load specs shared by the routes that serve a whole Session.

Both the detail route and the data export read a Session with its whole subtree,
and both had their own copy of the list. The risk is not the duplication itself
but the drift: a relationship added to one and not the other is not an error,
it is the same page served with one query per row.
"""

from sqlalchemy.orm import selectinload

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
