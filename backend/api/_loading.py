"""Shared Session loads, so eager-load lists cannot drift and ownership is a
filter in the query."""

import uuid

from sqlalchemy.orm import Session as DbSession, selectinload
from sqlalchemy.orm.interfaces import LoaderOption

from shared.db import models as db_models

SESSION_SUBTREE = (
    selectinload(db_models.Session.turns),
    selectinload(db_models.Session.measurements)
    .selectinload(db_models.Measurement.metric_type),
    # Down to the focus goal, or each tagged point costs a query.
    selectinload(db_models.Session.feedback)
    .selectinload(db_models.Feedback.points)
    .selectinload(db_models.FeedbackPoint.focus_goal),
    selectinload(db_models.Session.persona),
    selectinload(db_models.Session.scenario),
)

WITH_WRAPUP = (
    selectinload(db_models.Session.scenario),
    selectinload(db_models.Session.feedback).selectinload(db_models.Feedback.points),
)

FOR_RETRY = (
    selectinload(db_models.Session.feedback),
    selectinload(db_models.Session.turns),
    selectinload(db_models.Session.jobs),
)


def owned_session(
    db: DbSession, subject: str, extern_id: uuid.UUID, *loads: LoaderOption
) -> db_models.Session | None:
    """None for an absent id and for a foreign one alike (ADR 0050)."""
    return (
        db.query(db_models.Session)
        .filter_by(extern_id=extern_id, subject_id=subject)
        .options(*loads)
        .one_or_none()
    )
