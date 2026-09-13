"""Delete Sessions past the retention period, by hand (ADR 0067).

The app runs this sweep itself, daily, from its lifespan. This script is for
the times that is not enough: checking what the period would take before it
does, running it once after the period is changed, or clearing a backlog on an
instance that was down for a while.

    python scripts/apply_retention.py            # show what is over the line
    python scripts/apply_retention.py --apply    # delete it

Runs against the database in `.env`, so it works from a host shell as well as
inside the container -- unlike `requeue_feedback.py`, nothing here needs Redis.

Safe to run at any time and as often as anyone likes: it asks the database what
is expired, deletes that, and finds nothing on the second pass. It cannot
collide with the app's own sweep beyond one of the two finding the work already
done.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import UTC, datetime

from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

load_dotenv()

# After load_dotenv(): importing the backend reads the environment.
# pylint: disable=wrong-import-position
# The sys.path insert above has to run before the backend is importable, and
# load_dotenv() before it reads the environment -- so these cannot move up.
from backend import deletion, retention  # noqa: E402
from backend.db import models as db_models  # noqa: E402
from backend.db.session import session_scope  # noqa: E402
from backend.logging_config import configure_logging  # noqa: E402

logger = logging.getLogger(__name__)


def main() -> int:
    """Report, and with --apply delete, every Session past the period."""
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
        # Read inside the same transaction as the rows, so the report cannot
        # describe a preference that changed between the two queries.
        rows = [
            (str(s.extern_id), s.started_at, retention.auto_delete_enabled(db, s.subject_id))
            for s in expired
        ]
        # The reverse Scenarios that go with them (ADR 0070 as amended). Read
        # here for the same reason `deletion.reverses_of` reads them before the
        # delete: `origin_session_id` is `ON DELETE SET NULL`, so afterwards
        # nothing ties the two together. Counted for the report only -- the
        # sweep below does its own reading and its own deciding.
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
        # Named rather than left to the Session count: a dry run that does not
        # say everything --apply does is not a dry run. Some of these may
        # survive this pass -- `delete_unreferenced_reverses` leaves any row a
        # Session that has not expired is still played on -- so this is the
        # upper bound, which is the honest direction for a warning.
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
