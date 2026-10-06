"""The wrap-up worker (ADR 0018/0019): `python -m worker`."""

import logging

from rq import Worker

from shared.feedback.queue import QUEUE_NAME, connection
from shared.logging_config import configure_logging

logger = logging.getLogger(__name__)


def main() -> None:
    # RQ forks per job: Linux and macOS only.
    configure_logging()
    logger.info("Feedback worker starting, listening on %r", QUEUE_NAME)
    Worker([QUEUE_NAME], connection=connection()).work(with_scheduler=False)


if __name__ == "__main__":
    main()
