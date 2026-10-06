"""Re-queue wrap-ups for stored Sessions without one; --apply to queue. Run
inside the backend container (Redis is not published)."""

from __future__ import annotations

import argparse
import logging

from shared.db import models as db_models
from shared.feedback import jobs
from shared.db.session import session_scope
from shared.logging_config import configure_logging

logger = logging.getLogger(__name__)


def _candidates(db) -> list[tuple[int, str, int]]:
    found = []
    for session in db.query(db_models.Session).order_by(db_models.Session.session_id).all():
        # No job row qualifies too: the API reads it as failed.
        if jobs.retry_blocked(session) is None:
            found.append((session.session_id, str(session.extern_id), len(session.turns)))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true",
        help="actually enqueue; without it the script only reports",
    )
    args = parser.parse_args()
    configure_logging()

    with session_scope() as db:
        candidates = _candidates(db)

    if not candidates:
        logger.info("Nothing to re-queue: every stored Session with turns has a wrap-up.")
        return 0

    logger.info("%d Session(s) without a wrap-up:", len(candidates))
    for session_id, extern_id, turns in candidates:
        logger.info("  session %-4d %s  (%d turns)", session_id, extern_id, turns)

    if not args.apply:
        logger.info("Dry run. Re-run with --apply to queue these.")
        return 0

    # Imported here: reporting must not require Redis.
    from shared.feedback import queue  # pylint: disable=import-outside-toplevel

    queued = 0
    for session_id, extern_id, _turns in candidates:
        try:
            queue.enqueue_feedback(session_id)
        except Exception:  # pylint: disable=broad-except
            # One unreachable moment must not skip the rest of the backlog.
            logger.exception("Could not queue session %s; leaving its row as it is", extern_id)
            continue
        # Only after a successful enqueue, or the row lies.
        with session_scope() as db:
            jobs.mark(db, session_id, db_models.JOB_QUEUED)
        queued += 1

    logger.info("Queued %d of %d. The worker picks them up as it goes.", queued, len(candidates))
    return 0 if queued == len(candidates) else 1


if __name__ == "__main__":
    raise SystemExit(main())
