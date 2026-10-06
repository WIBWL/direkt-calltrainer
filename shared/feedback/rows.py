"""Measured figures into `measurement` rows. An unseeded key is logged and
dropped, not raised, which would lose every figure of the Session."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from decimal import Decimal

from sqlalchemy.orm import Session as DbSession

from shared.db import models as db_models
from shared.feedback.metrics import Measurement

logger = logging.getLogger(__name__)

# The scale `measurement.value` is stored at. One place, rather than the same
# format string in five: a change to the column's precision has one reader.
VALUE_SCALE = 4


def metric_ids(db: DbSession) -> dict[str, int]:
    """The seeded inventory, keyed by metric key."""
    return {row.key: row.metric_type_id for row in db.query(db_models.MetricType)}


def measurements(
    ids: Mapping[str, int],
    values: Iterable[Measurement],
    *,
    segment: str = db_models.SEGMENT_CALL,
    session_id: int | None = None,
) -> list[db_models.Measurement]:
    """Unattached rows for `values`, in order, skipping keys the seed lacks."""
    rows = []
    for value in values:
        metric_type_id = ids.get(value.key)
        if metric_type_id is None:
            logger.warning(
                "No seeded metric_type for %r; its figure is not stored", value.key
            )
            continue
        rows.append(db_models.Measurement(
            metric_type_id=metric_type_id,
            value=Decimal(f"{value.value:.{VALUE_SCALE}f}"),
            detail_json=value.detail,
            segment=segment,
            **({"session_id": session_id} if session_id is not None else {}),
        ))
    return rows
