"""Compute the interruption figures for Sessions stored before they existed (F-51).

    python scripts/backfill_interruptions.py            # show what would change
    python scripts/backfill_interruptions.py --apply    # write it

Possible because the Turn timeline is stored (the audio is not, ADR 0048). Uses the
database in `.env` (no Redis, no model). Idempotent; figures already written are
never recomputed, since the user has already been shown them."""

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
from backend.db import models as db_models  # noqa: E402
from backend.db.session import session_scope  # noqa: E402
from backend.feedback import interruptions, rows  # noqa: E402
from backend.feedback.metrics import Measurement  # noqa: E402
from scripts import _backfill_cli  # noqa: E402

logger = logging.getLogger("backfill_interruptions")


def _timeline(session: db_models.Session) -> tuple[interruptions.Segment, ...]:
    """The stored Turn rows as the classifier's segments, in `seq_index` order.

    Rows without a duration are dropped rather than guessed. No `dispatched_ms`: it is
    not stored, but for Sessions recorded before the live path measured this, the
    stored duration *is* the dispatched end; newer Sessions already have figures."""
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
        ids = _backfill_cli.metric_ids(db, logger, interruptions.COUNT_KEY)
        if ids is None:
            return 0
        count_id = ids[interruptions.COUNT_KEY]

        for session in _backfill_cli.each_session(db):
            # Skip what already carries the figure: this one fills a gap.
            if count_id in {m.metric_type_id for m in session.measurements}:
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

            session.measurements.extend(rows.measurements(
                {interruptions.COUNT_KEY: count_id},
                [Measurement(interruptions.COUNT_KEY, float(len(report.hard)), report.detail())],
                backfilled=True,
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
