"""The Feedback worker process (ADR 0018/0019).

A second deployable next to the FastAPI app, sharing its code and its database
but none of its request cycle: it takes one finished Session's id off the queue
and generates its wrap-up, so a slow or failing model can never affect a live call.

Run it with:  python -m backend.worker
"""

import logging

from rq import Worker

from backend.session import persistence
from backend.feedback.queue import QUEUE_NAME, connection
from backend.logging_config import configure_logging

logger = logging.getLogger(__name__)


def _work_horse_killed(job, retpid, ret_val, _rusage) -> None:
    """Mark feedback failed when the RQ work horse dies unexpectedly."""
    try:
        if not job.args:
            logger.error(
                "Killed feedback work horse had no session id: job=%s",
                job.id,
            )
            return

        session_id = int(job.args[0])

        persistence.mark_feedback_job_failed(
            session_id,
            (
                "Feedback worker terminated unexpectedly "
                f"(pid={retpid}, exit_status={ret_val})"
            ),
        )
    except Exception:
        logger.exception(
            "Could not mark feedback job failed after work horse termination"
        )


def main() -> None:
    """Configure logging, then block forever processing feedback jobs.

    RQ forks a child per job, so this only runs on Linux -- use the `worker`
    container, not a host process, on Windows (see CLAUDE.md).
    """
    # Its own file, not the app's: both mount the same logs/ directory, and
    # each process opens its log fresh on start (ADR 0055), so sharing one path
    # would have whichever booted second truncate the other's log.
    configure_logging("logs/worker.log")

    stale_jobs = persistence.fail_running_feedback_jobs(
        "Feedback worker restarted while this job was still running"
    )
    if stale_jobs:
        logger.warning(
            "Marked %d stale feedback job(s) failed on worker startup",
            stale_jobs,
        )

    logger.info("Feedback worker starting, listening on %r", QUEUE_NAME)
    Worker(
        [QUEUE_NAME],
        connection=connection(),
        work_horse_killed_handler=_work_horse_killed,
    ).work(with_scheduler=False)


if __name__ == "__main__":
    main()
