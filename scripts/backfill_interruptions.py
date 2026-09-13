"""Compute the interruption figures for Sessions stored before they existed (F-51).

    python scripts/backfill_interruptions.py            # show what would change
    python scripts/backfill_interruptions.py --apply    # write it

Possible at all because the *timeline* is persisted, unlike the audio: a Turn
row carries its speaker, its offset and its duration, which is everything
`interruptions.classify` reads. That makes this metric unusual in this project.
Speaking pace or loudness can never be recomputed for a past Session, because
ADR 0048 discards the recording the moment it has been measured; an overlap can,
because it is a property of when people spoke rather than of how they sounded.

Runs against the database in `.env`, so a host shell will do; nothing here needs
Redis or a model.

Idempotent. Sessions that already carry the figures are skipped, so a second run
reports nothing and changes nothing. Anything already written is left alone
rather than recomputed: a stored measurement is what the user has already been
shown, and quietly moving it under them would be worse than leaving one
generation of figures in place.
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
from backend.feedback import interruptions  # noqa: E402
from scripts import _backfill_cli  # noqa: E402

logger = logging.getLogger("backfill_interruptions")


def _timeline(session: db_models.Session) -> tuple[interruptions.Segment, ...]:
    """The stored Turn rows as the classifier's segments.

    Rows without a duration are dropped: an overlap cannot be established
    against a segment whose end is unknown, and assuming one would invent the
    measurement. Ordered by `seq_index`, which is the order they were spoken in
    and is unique per Session by constraint.
    """
    return tuple(
        interruptions.Segment(
            speaker=turn.speaker,
            offset_ms=turn.start_offset_ms,
            duration_ms=turn.duration_ms,
            interrupted=turn.interrupted,
        )
        for turn in sorted(session.turns, key=lambda t: t.seq_index)
        if turn.duration_ms
    )


def backfill(apply: bool) -> int:
    """Write the figures for every Session that has none. Returns how many."""
    written = 0
    with session_scope() as db:
        metric_ids = {m.key: m.metric_type_id for m in db.query(db_models.MetricType)}
        count_id = metric_ids.get(interruptions.COUNT_KEY)
        if count_id is None:
            logger.error("Metric inventory not seeded; run the app once first")
            return 0

        for session in db.query(db_models.Session).order_by(db_models.Session.session_id):
            existing = {m.metric_type_id for m in session.measurements}
            if count_id in existing:
                continue
            timeline = _timeline(session)
            if not timeline:
                continue

            report = interruptions.classify(timeline)
            logger.info(
                "Session %s: %d Persona-Beiträge, %d hart, %d weich, Ampel %s",
                session.extern_id, report.persona_turns, len(report.hard),
                len(report.soft), report.light.value,
            )
            if not apply:
                continue

            session.measurements.append(db_models.Measurement(
                metric_type_id=count_id,
                value=Decimal(f"{len(report.hard)}.0000"),
                # Marks the row as reconstructed rather than measured when the
                # call ended. The figures are identical either way, but a row
                # that says where it came from is worth the one key.
                detail_json={**report.detail(), "backfilled": True},
            ))
            session.findings.extend(
                db_models.Finding(
                    metric_type_id=count_id,
                    category=interruptions.FINDING_CATEGORY,
                    offset_ms=event.offset_ms,
                    description=interruptions.finding_description(event),
                )
                for event in report.hard
            )
            written += 1
    return written


def main() -> int:
    """CLI entry point. Returns the process exit code."""
    return _backfill_cli.run(backfill, __doc__.splitlines()[0], logger)


if __name__ == "__main__":
    raise SystemExit(main())
