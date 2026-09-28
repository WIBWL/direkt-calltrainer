"""Re-queue wrap-ups for Sessions that never got one (e.g. worker down, Redis lost the job).

    docker compose exec app python scripts/requeue_feedback.py           # dry run
    docker compose exec app python scripts/requeue_feedback.py --apply   # queue them

Run **inside the app container**: Redis is not published to the host. Written from the
stored Transcript and Measurements (ADR 0049), so old Sessions work. Safe to run twice;
eligibility is `jobs.retry_blocked`, shared with `POST /api/sessions/{id}/feedback`."""

from __future__ import annotations

import argparse
import logging
import os
import sys

from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

load_dotenv()

# After load_dotenv(): importing the backend reads the environment.
# pylint: disable=wrong-import-position
# The sys.path insert above has to run before the backend is importable, and
# load_dotenv() before it reads the environment -- so these cannot move up.
from backend.db import models as db_models  # noqa: E402
from backend.feedback import jobs  # noqa: E402
from backend.db.session import session_scope  # noqa: E402
from backend.logging_config import configure_logging  # noqa: E402

logger = logging.getLogger(__name__)

# Eligibility lives in `backend/feedback/jobs.py`, shared with the User's retry
# route, so the two cannot drift (a copy here once re-queued a running job).


def _candidates(db) -> list[tuple[int, str, int]]:
    """(session_id, extern_id, turn count) for every Session worth retrying.
    Sessions with no Turns are skipped -- there is nothing to write about."""
    found = []
    for session in db.query(db_models.Session).order_by(db_models.Session.session_id).all():
        # No job row at all qualifies too: api/sessions.py reads that as
        # "failed", so the Session is in the same dead end.
        if jobs.retry_blocked(session) is None:
            found.append((session.session_id, str(session.extern_id), len(session.turns)))
    return found


def main() -> int:
    """List, and with --apply re-queue, the Sessions still missing a wrap-up."""
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

    # Imported here, not at module scope: reporting must not require Redis.
    # `jobs` is imported up top -- it is the state machine and knows nothing of it.
    from backend.feedback import queue  # pylint: disable=import-outside-toplevel

    queued = 0
    for session_id, extern_id, _turns in candidates:
        try:
            queue.enqueue_feedback(session_id)
        except Exception:  # pylint: disable=broad-except
            # One unreachable moment must not skip the rest of the backlog.
            logger.exception("Could not queue session %s; leaving its row as it is", extern_id)
            continue
        # Only after the enqueue succeeded: a row saying `queued` with nothing
        # behind it is the exact state this script exists to repair.
        with session_scope() as db:
            jobs.mark(db, session_id, db_models.JOB_QUEUED)
        queued += 1

    logger.info("Queued %d of %d. The worker picks them up as it goes.", queued, len(candidates))
    return 0 if queued == len(candidates) else 1


if __name__ == "__main__":
    raise SystemExit(main())
