"""Compute the call closing for Sessions stored before it existed (ADR 0089).

    python scripts/backfill_closing.py            # show what would change
    python scripts/backfill_closing.py --apply    # write it

Possible because the closing is read from words alone. The user's last two
utterances are stored as transcript rows on the `turn` table, the Session keeps
its language, and `metrics.closing_parts` is the same function the live path
runs -- so a figure written here is the figure the call would have got had the
metric existed when it ended. None of it needs the recording, which ADR 0048
discards the moment it has been measured.

That makes this the third metric that can reach backwards, after the
interruptions of F-51 and the Sprechlänge am Stück of F-53.

Runs against the database in `.env`, so a host shell will do; nothing here needs
Redis or a model.

Idempotent. Sessions that already carry the figure are skipped, so a second run
reports nothing and changes nothing. Sessions with fewer than three user
utterances are skipped too, exactly as the live path skips them: a call hung up
after a sentence or two has no closing to read.
"""

# pylint: disable=duplicate-code
# What is left once `_backfill_cli` took the command line is this module's own
# entry point: `main()` delegating, and the `if __name__` guard. A script
# cannot share its own entry point.


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
from backend.db import models as db_models  # noqa: E402
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
        closing_id = (
            db.query(db_models.MetricType.metric_type_id)
            .filter(db_models.MetricType.key == metrics.CLOSING_KEY)
            .scalar()
        )
        if closing_id is None:
            logger.error("Metric inventory not seeded; run the app once first")
            return 0

        for session in db.query(db_models.Session).order_by(db_models.Session.session_id):
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
