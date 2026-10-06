"""Report, or with --apply delete, Sessions past the retention period (ADR 0067)."""

from __future__ import annotations

import argparse
import logging
from datetime import UTC, datetime

from shared.db import models as db_models
from shared.db.session import session_scope
from shared.logging_config import configure_logging
from backend import deletion, retention

logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true",
        help="actually delete; without it the script only reports",
    )
    args = parser.parse_args()
    configure_logging()

    now = datetime.now(UTC)
    boundary = retention.cutoff(now)
    logger.info("Retention is %d days; anything started before %s is due.",
                retention.RETENTION.days, boundary.date())

    with session_scope() as db:
        expired = (
            db.query(db_models.Session)
            .filter(db_models.Session.started_at < boundary)
            .order_by(db_models.Session.started_at)
            .all()
        )
        rows = [
            (str(s.extern_id), s.started_at, retention.auto_delete_enabled(db, s.subject_id))
            for s in expired
        ]
        # Read now: afterwards SET NULL unties them. For the report only.
        due_sessions = [s for s in expired if retention.auto_delete_enabled(db, s.subject_id)]
        reverses = len(deletion.reverses_of(db, due_sessions))

    if not rows:
        logger.info("Nothing is past the retention period.")
        return 0

    for extern_id, started, swept in rows:
        logger.info("  %s  started %s  %s",
                    extern_id, started.date(), "due" if swept else "kept (sweep suspended)")

    due = sum(1 for _, _, swept in rows if swept)
    if reverses:
        # An upper bound: reverses still played by unexpired Sessions survive.
        logger.info("  plus up to %d reverse scenario(s) built from those calls.", reverses)
    if not args.apply:
        logger.info("Dry run: %d of %d session(s) would be deleted. Re-run with --apply.",
                    due, len(rows))
        return 0

    with session_scope() as db:
        deleted = retention.sweep(db, now=now)
    logger.info("Deleted %d session(s).", deleted)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
