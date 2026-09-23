"""Shared command line and table scan for the backfill scripts.

They differ only in which figure they compute; the CLI around it -- the
`--apply` flag, the dry-run wording, the exit code -- was the same in all of
them down to the character. Reworded in one place it would have applied to one
script and left the others saying something else.

`metric_ids` and `each_session` are the same argument one level in. All four
scripts looked the inventory up, refused with the same sentence when it was
not seeded, and walked the `session` table in the same order; three of them
wrote that sentence out a fourth time. The scan also carries what a backfill
reads, which none of them asked for -- so each one paid a query per Session
for its measurements and another for its turns.

What deliberately stays per script is the skip: three of them pass over a
Session that already carries the figure, and `backfill_opening.py` passes over
one that does not, because it rewrites a figure rather than filling a gap.
That is the line between them, so it is written where it differs.

`backfill_opening.py` stretches the name a little: it rewrites a figure that is
already there, rather than filling a gap, because the patterns behind it
changed. The command line it needs is the same one.

Imported after each script's `sys.path` insert, like the `backend` imports
beside it, so `scripts` resolves as a namespace package from the project root.
"""

import argparse
import logging
from collections.abc import Callable, Iterator

from sqlalchemy.orm import Session as DbSession, selectinload

from backend.db import models as db_models
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


def metric_ids(
    db: DbSession, logger: logging.Logger, *required: str
) -> dict[str, int] | None:
    """Every metric id by key, or None if one of `required` is not seeded.

    Returns the whole inventory rather than the keys asked for: a backfill that
    reads another metric's stored detail -- `backfill_run_length.py` divides
    figures `phonation_share` and `pauses` left behind -- needs the map anyway,
    and handing back a second shape for that case would be two functions
    saying one thing.

    The refusal is logged here because all four scripts logged it, in the same
    words, and a reworded one would have reached whichever was edited.
    """
    ids = {m.key: m.metric_type_id for m in db.query(db_models.MetricType)}
    missing = [key for key in required if key not in ids]
    if missing:
        logger.error("Metric inventory not seeded; run the app once first")
        return None
    return ids


def each_session(db: DbSession) -> Iterator[db_models.Session]:
    """Every stored Session, oldest first, with what a backfill reads loaded.

    The order is by primary key, so a run reports in the order the Sessions
    were stored and two runs report alike.

    The three relationships are the ones all four backfills walk: the
    measurements they check for the figure, the turns they read the transcript
    off, and the Scenario whose `reverse` decides how an opening is read. Left
    lazy, each of those cost a query per Session -- invisible on a developer's
    handful of them, and a few thousand queries on six months of calls.
    """
    yield from (
        db.query(db_models.Session)
        .options(
            selectinload(db_models.Session.measurements),
            selectinload(db_models.Session.turns),
            selectinload(db_models.Session.scenario),
        )
        .order_by(db_models.Session.session_id)
    )
