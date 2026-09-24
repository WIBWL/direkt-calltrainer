"""Re-read the call opening of stored Sessions with today's patterns (F-63).

    python scripts/backfill_opening.py            # show what would change
    python scripts/backfill_opening.py --apply    # write it

Rewrites rather than fills: only the three word-based parts (`metrics.opening_parts`);
the acoustic `pace_ratio` is carried over (no audio, ADR 0048). Uses `.env`'s database
(no Redis, no model). Unchanged Sessions are skipped, so a second run reports nothing."""

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
