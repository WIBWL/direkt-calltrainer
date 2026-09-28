"""The Feedback worker process (ADR 0018/0019): the shared code and the same
database as the app, no request cycle. Generates one finished Session's wrap-up
per queued job, so a slow model never affects a live call.

Run it with:  python -m worker"""

import logging

from rq import Worker

from shared.feedback.queue import QUEUE_NAME, connection
from shared.logging_config import configure_logging

logger = logging.getLogger(__name__)


def main() -> None:
    """Configure logging, then block forever processing feedback jobs.

    RQ forks a child per job, so this runs on Linux and macOS but not on
    Windows -- run the worker image there instead (see CLAUDE.md).
    """
    configure_logging()
    logger.info("Feedback worker starting, listening on %r", QUEUE_NAME)
    Worker([QUEUE_NAME], connection=connection()).work(with_scheduler=False)


if __name__ == "__main__":
    main()
