"""Re-queue wrap-ups for Sessions that never got one.

A Session's wrap-up is generated in the RQ worker (ADR 0018/0019), and the job
lives in Redis while the row that tracks it lives in Postgres (ADR 0032). The
two can come apart: if the worker is down when a call ends, or Redis loses the
job, the database keeps saying `queued` and nothing will ever pick it up. The
history then shows "Feedback wird erstellt" forever, which is the one thing
that screen must not say untruthfully.

This puts those Sessions back on the queue. Nothing needs regenerating from
audio -- the wrap-up is written from the stored Transcript and Measurements
(ADR 0049), both of which are still there, which is why a Session from days ago
can still be analysed.

    docker compose exec app python scripts/requeue_feedback.py           # dry run
    docker compose exec app python scripts/requeue_feedback.py --apply   # queue them

Run it **inside the app container**. Redis is only reachable on the compose
network -- compose.yaml deliberately does not publish it to the host -- so the
reporting half of this script works from a host shell and the `--apply` half
does not.

Safe to run twice: a Session that already has a wrap-up is never selected, so a
second run after a successful one does nothing.
"""

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
from backend.db import models as db_models  # noqa: E402
from backend.db.session import session_scope  # noqa: E402
from backend.logging_config import configure_logging  # noqa: E402

logger = logging.getLogger(__name__)

# A Session whose job never finished. `running` is included because a worker
# killed mid-job leaves the row there with nothing to move it (ADR 0032 names
# this gap), and `failed` because a wrap-up that failed on a dead gateway is
# worth another attempt once the gateway is back.
RETRYABLE = (db_models.JOB_QUEUED, db_models.JOB_RUNNING, db_models.JOB_FAILED)


def _candidates(db) -> list[tuple[int, str, int]]:
    """(session_id, extern_id, turn count) for every Session worth retrying.

    A Session with no Turns is skipped: there is nothing to write a wrap-up
    about, and asking a model to summarise an empty conversation produces a
    paragraph that describes nothing. Those rows are left as they are — their
    status is accurate.
    """
    found = []
    for session in db.query(db_models.Session).order_by(db_models.Session.session_id).all():
        if session.feedback is not None:
            continue
        if not session.turns:
            continue
        jobs = [j for j in session.jobs if j.kind == db_models.JOB_KIND_FEEDBACK]
        newest = max(jobs, key=lambda j: j.job_id) if jobs else None
        # No job row at all also qualifies: api/sessions.py reads that as
        # "failed", so the Session is in the same dead end.
        if newest is None or newest.status in RETRYABLE:
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
    from backend.feedback import jobs, queue  # pylint: disable=import-outside-toplevel

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
