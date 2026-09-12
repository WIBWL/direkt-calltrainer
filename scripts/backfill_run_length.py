"""Compute the Sprechlänge am Stück for Sessions stored before it existed (F-53).

    python scripts/backfill_run_length.py            # show what would change
    python scripts/backfill_run_length.py --apply    # write it

Possible at all because everything this metric divides was already stored by
two other metrics. `phonation_share` keeps `phonation_ms` in its detail,
`pauses` keeps a `count`, and the number of utterances is a row count on the
`turn` table. None of it needs the recording, which ADR 0048 discards the moment
it has been measured.

That makes this the second metric in the project that can reach backwards, after
the interruptions of F-51, and for the same underlying reason: it is a property
of when somebody spoke rather than of how they sounded. Speaking pace, loudness
and intonation can never be recomputed for a past Session.

Runs against the database in `.env`, so a host shell will do; nothing here needs
Redis or a model.

Idempotent. Sessions that already carry the figure are skipped, so a second run
reports nothing and changes nothing.
"""

# pylint: disable=duplicate-code
# What is left once `_backfill_cli` took the command line is this module's own
# entry point: `main()` delegating, and the `if __name__` guard. A script
# cannot share its own entry point.


from __future__ import annotations

import logging
import os
import sys
from decimal import Decimal

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
from backend.feedback import metrics  # noqa: E402
from scripts import _backfill_cli  # noqa: E402

logger = logging.getLogger("backfill_run_length")


def _terms(session: db_models.Session, by_id: dict[int, str]) -> tuple[int, int, int] | None:
    """Phonation, utterances and pauses for one Session, or None if unusable.

    The presence of a `phonation_share` row is the gate, and it is the right
    one: that metric is withheld for the whole call when any Turn's measurement
    failed (ADR 0051), so a Session carrying it has complete acoustics and one
    without it could only be backfilled with a figure short by an unknown
    amount.

    A Session with no `pauses` row spoke without pausing inside an utterance,
    which is nought pauses and not missing data. Absence and zero mean the same
    thing here, unlike above.
    """
    phonation: int | None = None
    pause_count = 0
    for measurement in session.measurements:
        key = by_id.get(measurement.metric_type_id)
        if key == "phonation_share":
            phonation = (measurement.detail_json or {}).get("phonation_ms")
        elif key == "pauses":
            pause_count = (measurement.detail_json or {}).get("count", 0)

    utterances = sum(1 for turn in session.turns if turn.speaker == db_models.SPEAKER_USER)
    if not phonation or not utterances:
        return None
    return phonation, utterances, pause_count


def backfill(apply: bool) -> int:
    """Write the figure for every Session that has none. Returns how many."""
    written = 0
    with session_scope() as db:
        by_key = {m.key: m.metric_type_id for m in db.query(db_models.MetricType)}
        by_id = {v: k for k, v in by_key.items()}
        run_id = by_key.get(metrics.RUN_LENGTH_KEY)
        if run_id is None:
            logger.error("Metric inventory not seeded; run the app once first")
            return 0

        for session in db.query(db_models.Session).order_by(db_models.Session.session_id):
            if run_id in {m.metric_type_id for m in session.measurements}:
                continue
            terms = _terms(session, by_id)
            if terms is None:
                continue

            phonation, utterances, pause_count = terms
            runs = utterances + pause_count
            seconds = phonation / runs / 1000
            logger.info(
                "Session %s: %.1f s Sprechzeit auf %d Abschnitte (%d Äußerungen, "
                "%d Pausen) = %.2f s",
                session.extern_id, phonation / 1000, runs, utterances, pause_count, seconds,
            )
            if not apply:
                continue

            session.measurements.append(db_models.Measurement(
                metric_type_id=run_id,
                value=Decimal(f"{seconds:.4f}"),
                detail_json={
                    "runs": runs,
                    "phonation_ms": phonation,
                    "utterances": utterances,
                    "pause_count": pause_count,
                    # Marks the row as reconstructed rather than measured when
                    # the call ended. The figure is identical either way, but a
                    # row that says where it came from is worth the one key.
                    "backfilled": True,
                },
            ))
            written += 1
    return written


def main() -> int:
    """CLI entry point. Returns the process exit code."""
    return _backfill_cli.run(backfill, __doc__.splitlines()[0], logger)


if __name__ == "__main__":
    raise SystemExit(main())
