"""Compute the call closing for Sessions stored before it existed (ADR 0089).

    python scripts/backfill_closing.py            # show what would change
    python scripts/backfill_closing.py --apply    # write it

Read from the stored transcript via `metrics.closing_parts`, no audio needed. Uses the
database in `.env` (no Redis, no model). Idempotent; skips Sessions that already carry
the figure or have fewer than three user utterances, as the live path does."""

# pylint: disable=duplicate-code
# The sys.path preamble and the main()/__name__ guard cannot move into
# `_backfill_cli`: the preamble must run before that import.


from __future__ import annotations

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
from backend.db.session import session_scope  # noqa: E402
from backend.feedback import metrics, rows, stored  # noqa: E402
from backend.session.language_packs import LANGUAGE_PACKS  # noqa: E402
from scripts import _backfill_cli  # noqa: E402

logger = logging.getLogger("backfill_closing")

# How the three parts are named in the report, in the order the tile shows them.
_LABELS = {"recap": "Zusammenfassung", "agreement": "Vereinbarung", "farewell": "Verabschiedung"}


def backfill(apply: bool) -> int:
    """Write the figure for every Session that has none. Returns how many."""
    written = 0
    with session_scope() as db:
        ids = _backfill_cli.metric_ids(db, logger, metrics.CLOSING_KEY)
        if ids is None:
            return 0
        closing_id = ids[metrics.CLOSING_KEY]

        for session in _backfill_cli.each_session(db):
            # Skip what already carries the figure: this one fills a gap.
            if closing_id in {m.metric_type_id for m in session.measurements}:
                continue
            pack = LANGUAGE_PACKS.get(session.language_code)
            if pack is None:
                continue
            parts = metrics.closing_parts(stored.user_texts(session), pack)
            if parts is None:
                continue

            found = ", ".join(_LABELS[key] for key, said in parts.items() if said) or "nichts"
            logger.info("Session %s: erkannt %s", session.extern_id, found)
            if not apply:
                continue

            session.measurements.extend(rows.measurements(
                {metrics.CLOSING_KEY: closing_id},
                [metrics.closing_measurement(parts)],
                backfilled=True,
            ))
            written += 1
    return written


def main() -> int:
    """CLI entry point. Returns the process exit code."""
    return _backfill_cli.run(backfill, __doc__.splitlines()[0], logger)


if __name__ == "__main__":
    raise SystemExit(main())
