"""Shared command line for the backfill scripts.

The three of them differ only in which figure they compute; the CLI around it --
the `--apply` flag, the dry-run wording, the exit code -- was the same in all
three down to the character. Reworded in one place it would have applied to one
script and left the other two saying something else.

Imported after each script's `sys.path` insert, like the `backend` imports
beside it, so `scripts` resolves as a namespace package from the project root.
"""

import argparse
import logging
from collections.abc import Callable

from backend.logging_config import configure_logging


def run(backfill: Callable[[bool], int], description: str, logger: logging.Logger) -> int:
    """Parse `--apply`, run `backfill`, say what it did. Returns the exit code.

    `logger` belongs to the calling script rather than to this module, so the
    lines still carry the name of the backfill the reader started.
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--apply", action="store_true",
                        help="write the figures; without it, only report")
    args = parser.parse_args()
    configure_logging()

    written = backfill(args.apply)
    if args.apply:
        logger.info("%d Session(s) nachgerechnet", written)
    else:
        logger.info("Probelauf, nichts geschrieben. Mit --apply ausführen.")
    return 0
