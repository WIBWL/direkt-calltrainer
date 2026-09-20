"""Turning measured figures into the rows that store them.

`metrics.py` measures and knows nothing of the database; this is the other half
of that split -- the one place a `Measurement` value becomes a `measurement`
row. Four writers needed it and each wrote it out: the live path
(`session/persistence.py`), the wrap-up's segment pass
(`feedback/generator.py`) and the backfill scripts, every one of them with its
own copy of the metric-id lookup, the same `Decimal(f"{value:.4f}")` and the
same silent drop of a key the inventory does not know.

Silent is what it no longer is. A metric whose key is not seeded cannot be
stored -- the row it would point at does not exist -- but a figure vanishing
from every Session with a passing test suite is the kind of failure this
application is least able to see, so it is logged with the key that caused it.
Dropping rather than raising stays: the alternative is losing the whole
Session's statistics, and provision.py seeds the inventory from the same
`METRICS` tuple, so this can only happen against a database behind the code.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from decimal import Decimal

from sqlalchemy.orm import Session as DbSession

from backend.db import models as db_models
from backend.feedback.metrics import Measurement

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
    backfilled: bool = False,
) -> list[db_models.Measurement]:
    """Unattached rows for `values`, in order, skipping keys the seed lacks.

    Unattached on purpose: the live path assigns them to `session.measurements`
    and the segment pass adds them by `session_id`, and a helper that picked one
    of those would be a writer with a flag rather than a shared shape.

    `backfilled` marks a row as reconstructed rather than measured when the call
    ended. The figure is identical either way, but a row that says where it came
    from is worth the one key.
    """
    rows = []
    for value in values:
        metric_type_id = ids.get(value.key)
        if metric_type_id is None:
            logger.warning(
                "No seeded metric_type for %r; its figure is not stored", value.key
            )
            continue
        detail = value.detail or {}
        rows.append(db_models.Measurement(
            metric_type_id=metric_type_id,
            value=Decimal(f"{value.value:.{VALUE_SCALE}f}"),
            detail_json=(detail | {"backfilled": True}) if backfilled else value.detail,
            segment=segment,
            **({"session_id": session_id} if session_id is not None else {}),
        ))
    return rows
