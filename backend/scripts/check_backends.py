"""The boot check from the command line; exit 0 only if every backend responds."""

import asyncio
import sys

from shared.logging_config import configure_logging
from backend.clients.health import check_backends


def main() -> int:
    configure_logging()
    return 0 if asyncio.run(check_backends()) else 1


if __name__ == "__main__":
    sys.exit(main())
