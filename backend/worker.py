"""The Feedback worker process (ADR 0018/0019).

A second deployable next to the FastAPI app, sharing its code and its database
but none of its request cycle: it takes one finished Session's id off the queue
and generates its wrap-up, so a slow or failing model can never affect a live call.

Run it with:  python -m backend.worker
"""

import logging

from rq import Worker

from backend.feedback.queue import QUEUE_NAME, connection
from backend.logging_config import configure_logging

logger = logging.getLogger(__name__)


def main() -> None:
    """Configure logging, then block forever processing feedback jobs.

    RQ forks a child per job, so this only runs on Linux -- use the `worker`
    container, not a host process, on Windows (see CLAUDE.md).
    """
    # Its own file, not the app's: both mount the same logs/ directory, and
    # each process opens its log fresh on start (ADR 0055), so sharing one path
    # would have whichever booted second truncate the other's log.
    configure_logging("logs/worker.log")
    logger.info("Feedback worker starting, listening on %r", QUEUE_NAME)
    Worker([QUEUE_NAME], connection=connection()).work(with_scheduler=False)


if __name__ == "__main__":
    main()
