"""Re-read the call opening of stored Sessions with today's patterns (F-63).

    python scripts/backfill_opening.py            # show what would change
    python scripts/backfill_opening.py --apply    # write it

Unlike the other backfills this one does not fill a gap: every stored Session
already carries an opening. What it does is read that opening *again*, because
the patterns behind it have changed -- the frames a name is said in were
widened after "Guten Tag, hier ist die Anna" came back as no introduction, and
every call recorded before that still says so on screen.

That is only possible for the three parts, and only they are rewritten. They
are read from words, and the words are on the `turn` table
(`metrics.opening_parts` is the same function the live path runs). The tempo of
the opening against the rest of the call is acoustic, the recording is gone
(ADR 0048), and the stored `pace_ratio` is therefore carried over untouched
rather than recomputed or dropped.

Runs against the database in `.env`, so a host shell will do; nothing here needs
Redis or a model.

Idempotent in the sense that matters: a Session whose parts come out exactly as
they are stored is left alone and not reported, so a second run after --apply
reports nothing. It is *not* idempotent across a pattern change, which is the
whole point of it.
"""

# pylint: disable=duplicate-code
# What is left, once `_backfill_cli` took the command line, the inventory
# lookup and the table scan, is what a script cannot hand away: the preamble
# that makes `backend` and `scripts` importable at all -- the `sys.path`
# insert has to run before the import that would share it -- and this module's
# own entry point, `main()` delegating plus the `if __name__` guard.


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
from backend.feedback import metrics, stored  # noqa: E402
from backend.session.language_packs import LANGUAGE_PACKS  # noqa: E402
from scripts import _backfill_cli  # noqa: E402

logger = logging.getLogger("backfill_opening")

# How the parts are named in the report. Four keys for three parts: exactly one
# of offer and concern applies, decided by who rang (ADR 0086).
_LABELS = {
    "greeting": "Begrüßung",
    "name": "Name",
    "offer": "Hilfsangebot",
    "concern": "Anliegen",
}


def _said(parts: dict[str, bool]) -> str:
    """The recognised parts in words, for the report."""
    return ", ".join(_LABELS[key] for key, found in parts.items() if found) or "nichts"


def backfill(apply: bool) -> int:
    """Re-read every stored opening. Returns how many came out differently."""
    changed = 0
    with session_scope() as db:
        ids = _backfill_cli.metric_ids(db, logger, "opening")
        if ids is None:
            return 0
        opening_id = ids["opening"]

        for session in _backfill_cli.each_session(db):
            # The other way round from the three backfills beside this one: no
            # row means nothing to rewrite, because this run corrects a figure
            # the call already got rather than supplying one it never had.
            existing = next(
                (m for m in session.measurements if m.metric_type_id == opening_id), None
            )
            if existing is None:
                continue
            pack = LANGUAGE_PACKS.get(session.language_code)
            # The first row of the user's, not of the call's: the Persona's
            # own opening line is a row of its own and not this one.
            spoken = stored.user_texts(session)
            first = spoken[0] if spoken else None
            if pack is None or first is None:
                continue

            # `scenario.reverse` decides the third part, and it is on the row
            # the Session was played on -- the same source the live path reads.
            parts = metrics.opening_parts(
                first, pack, reverse=bool(session.scenario and session.scenario.reverse)
            )
            detail = dict(existing.detail_json or {})
            before = {key: bool(detail.get(key)) for key in parts}
            if before == parts:
                continue

            logger.info(
                "Session %s: %s  ->  %s", session.extern_id, _said(before), _said(parts)
            )
            changed += 1
            if not apply:
                continue

            # The acoustic half is carried over: `pace_ratio` was measured from
            # audio that no longer exists, and dropping it would lose a figure
            # this run has no way to produce again.
            existing.detail_json = detail | parts
            existing.value = float(sum(parts.values()))
    return changed


def main() -> int:
    """CLI entry point. Returns the process exit code."""
    return _backfill_cli.run(backfill, __doc__.splitlines()[0], logger)


if __name__ == "__main__":
    raise SystemExit(main())
