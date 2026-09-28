"""Check the pipeline backends (STT, LLM, TTS) from the host, with the same check
the app runs at startup (`backend.clients.health.check_backends`, ADR 0103).

Usage:
    python -m backend.scripts.check_backends      # exit 0 only if every backend responds"""

import asyncio
import sys

from shared.logging_config import configure_logging
from backend.clients.health import check_backends


def main() -> int:
    """Check every backend, log a line each, return a shell exit code."""
    configure_logging()
    return 0 if asyncio.run(check_backends()) else 1


if __name__ == "__main__":
    sys.exit(main())
