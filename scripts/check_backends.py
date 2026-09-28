"""Check the pipeline backends (STT, LLM, TTS) from the host, with the same check
the app runs at startup (`backend.clients.health.check_backends`, ADR 0103).

Usage:
    python scripts/check_backends.py      # exit 0 only if every backend responds"""

import asyncio
import os
import sys

from dotenv import load_dotenv

# A script, not a package: the project root has to be on the search path
# before `backend` can be imported, hence the position marker on that import.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from backend.clients.health import check_backends  # noqa: E402  # pylint: disable=wrong-import-position
from backend.logging_config import configure_logging  # noqa: E402  # pylint: disable=wrong-import-position


def main() -> int:
    """Check every backend, log a line each, return a shell exit code."""
    load_dotenv()
    configure_logging()
    return 0 if asyncio.run(check_backends()) else 1


if __name__ == "__main__":
    sys.exit(main())
