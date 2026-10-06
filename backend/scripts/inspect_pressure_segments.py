"""How the wrap-up marked demanding stretches (ADR 0081), which no test can judge.
Everything or nothing marked, call after call, is the warning sign. Read-only.

    python -m backend.scripts.inspect_pressure_segments [--session <id>] [--transcript]
"""

from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy.exc import ProgrammingError

from shared.db import models as db_models
from shared.db.session import session_scope
from shared.logging_config import configure_logging

logger = logging.getLogger("inspect_pressure_segments")

_EXCERPT = 90


class _Row:

    # pylint: disable=too-many-instance-attributes  # one field per column
    def __init__(self, session: db_models.Session) -> None:
        turns = sorted(session.turns, key=lambda t: t.seq_index)
        self.extern_id = str(session.extern_id)
        self.scenario = session.scenario.title
        self.persona = session.persona.name
        self.started_at = session.started_at
        self.has_feedback = session.feedback is not None
        self.persona_turns = [t for t in turns if t.speaker == db_models.SPEAKER_PERSONA]
        self.pressed = [t for t in self.persona_turns if t.pressed]
        # All NULL = unjudged, which must not read like "nothing pressing".
        self.judged = any(t.pressed is not None for t in self.persona_turns)
        self.has_facts = any(
            t.acoustics_json for t in turns if t.speaker == db_models.SPEAKER_USER
        )
        self.segments = sorted({
            m.segment for m in session.measurements
            if m.segment != db_models.SEGMENT_CALL
        })
        self.turns = turns

    @property
    def rate(self) -> float | None:
        if not self.persona_turns or not self.judged:
            return None
        return len(self.pressed) / len(self.persona_turns)

    @property
    def verdict(self) -> str:
        """One greppable word; "nobody pushed back" never collapses into "unjudged"."""
        # pylint: disable=too-many-return-statements  # one per state
        if not self.has_facts:
            return "no-facts"       # no measured user utterance
        if not self.has_feedback:
            return "no-wrapup"      # the job never finished, so nothing was judged
        if not self.judged:
            return "unjudged"       # a wrap-up that answered without the key
        if not self.pressed:
            return "none-pressing"
        if len(self.pressed) == len(self.persona_turns):
            return "ALL-pressing"   # suspicious: look at this one
        if not self.segments:
            return "too-short"      # marked, but a stretch fell under the floor
        return "ok"


def _load(extern_id: str | None) -> list[_Row]:
    with session_scope() as db:
        query = db.query(db_models.Session).order_by(db_models.Session.started_at.desc())
        if extern_id:
            query = query.filter(db_models.Session.extern_id == extern_id)
        return [_Row(session) for session in query.all()]


def _report(rows: list[_Row]) -> None:
    logger.info(
        "%-38s %-24s %-10s %-14s %s",
        "Session", "Szenario", "Druck", "Abschnitte", "Befund",
    )
    for row in rows:
        rate = "-" if row.rate is None else f"{len(row.pressed)}/{len(row.persona_turns)}"
        logger.info(
            "%-38s %-24s %-10s %-14s %s",
            row.extern_id,
            row.scenario[:24],
            rate,
            ",".join(row.segments) or "-",
            row.verdict,
        )


def _transcript(row: _Row) -> None:
    """The trainee's answer is shown under the line it answers."""
    logger.info("")
    logger.info("%s -- %s mit %s", row.extern_id, row.scenario, row.persona)
    logger.info("Befund: %s", row.verdict)
    for turn in row.turns:
        if turn.speaker == db_models.SPEAKER_PERSONA:
            mark = ">> DRUCK" if turn.pressed else "        "
            who = "Persona"
        else:
            mark = "        "
            who = "Nutzer "
        logger.info("%s %s: %s", mark, who, turn.transcript[:_EXCERPT])


def _summary(rows: list[_Row]) -> None:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.verdict] = counts.get(row.verdict, 0) + 1
    logger.info("")
    logger.info("%d Sitzung(en):", len(rows))
    for verdict, count in sorted(counts.items()):
        logger.info("  %-14s %d", verdict, count)

    judged = [row for row in rows if row.rate is not None]
    if judged:
        average = sum(row.rate for row in judged) / len(judged)
        logger.info("")
        logger.info(
            "Im Mittel sind %.0f%% der Persona-Beiträge als fordernd markiert (%d Sitzungen).",
            average * 100, len(judged),
        )
        # A single `%`: logging only escapes it when given arguments.
        logger.info(
            "Nahe 0% oder nahe 100% ist das Warnzeichen: Dann vergleicht die Anzeige "
            "zwei Abschnitte, die keine zwei sind."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", help="nur diese Sitzung (extern_id)")
    parser.add_argument(
        "--transcript", action="store_true",
        help="die markierten Zeilen im Wortlaut zeigen",
    )
    args = parser.parse_args()

    configure_logging()
    try:
        rows = _load(args.session)
    except ProgrammingError as e:
        # Usually a database a migration behind; the app migrates at startup.
        if "acoustics_json" in str(e) or "segment" in str(e):
            logger.error(
                "Die Datenbank kennt die Spalten aus ADR 0081 noch nicht. "
                "Einmal `docker compose up --build` starten -- die Anwendung "
                "migriert beim Hochfahren selbst -- und dann erneut versuchen."
            )
            sys.exit(1)
        raise
    if not rows:
        logger.info("Keine Sitzung gefunden.")
        return

    _report(rows)
    if args.transcript or args.session:
        for row in rows:
            _transcript(row)
    _summary(rows)


if __name__ == "__main__":
    main()
