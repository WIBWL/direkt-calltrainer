"""Shared command line (`--apply`, dry-run wording, exit code), metric lookup and
table scan for the backfill scripts, so they cannot drift apart. The skip rule stays
per script (`backfill_opening.py` rewrites rather than fills). Imported after each
script's `sys.path` insert, so `scripts` resolves as a namespace package.
"""

import argparse
import logging
from collections.abc import Callable, Iterator

from sqlalchemy.orm import Session as DbSession, selectinload

from backend.db import models as db_models
from backend.logging_config import configure_logging


def run(backfill: Callable[[bool], int], description: str, logger: logging.Logger) -> int:
    """Parse `--apply`, run `backfill`, say what it did. Returns the exit code.

    `logger` belongs to the calling script rather than to this module, so the
    lines still carry the name of the backfill the reader started.
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--apply", action="store_true",
                        help="write the figures; without it, only report")
    args = parser.parse_args()
    configure_logging()

    written = backfill(args.apply)
    if args.apply:
        logger.info("%d Session(s) nachgerechnet", written)
    else:
        logger.info("Probelauf, nichts geschrieben. Mit --apply ausführen.")
    return 0


def metric_ids(
    db: DbSession, logger: logging.Logger, *required: str
) -> dict[str, int] | None:
    """Every metric id by key, or None (logged) if one of `required` is not seeded.

    The whole inventory, since e.g. `backfill_run_length.py` reads other
    metrics' stored details."""
    ids = {m.key: m.metric_type_id for m in db.query(db_models.MetricType)}
    missing = [key for key in required if key not in ids]
    if missing:
        logger.error("Metric inventory not seeded; run the app once first")
        return None
    return ids


def each_session(db: DbSession) -> Iterator[db_models.Session]:
    """Every stored Session, oldest first (by primary key, so runs report alike),
    with measurements, turns and Scenario eager-loaded -- lazy, each cost a query
    per Session."""
    yield from (
        db.query(db_models.Session)
        .options(
            selectinload(db_models.Session.measurements),
            selectinload(db_models.Session.turns),
            selectinload(db_models.Session.scenario),
        )
        .order_by(db_models.Session.session_id)
    )
