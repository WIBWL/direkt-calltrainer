"""Read back how the wrap-up split a call into demanding stretches and the rest
(F-62, ADR 0081).

    python scripts/inspect_pressure_segments.py                 # every stored Session
    python scripts/inspect_pressure_segments.py --session <id>  # one, with its transcript
    python scripts/inspect_pressure_segments.py --transcript    # all of them, with transcripts

The one thing about this feature that no test can answer. Whether a marked
utterance really was demanding is a judgement about what was said, made by a
language model, and the only way to check it is to read the lines it marked
beside the ones it did not.

Two failure modes are what to look for, and both leave the application working
and the screen plausible:

* **Everything marked.** The two stretches are then the same stretch measured
  twice, and the comparison shows a difference of nearly zero, which reads as
  "very composed" to anybody who does not know.
* **Nothing marked, call after call.** Either the calls genuinely had no push
  back in them -- entirely possible with the gentler Personas -- or the model is
  dropping the key. The summary below separates those two by showing how often
  it happens and on which Scenario.

The rate column is the quick read: a call where the partner pushed in every
single one of its turns, or in none of a dozen, is worth opening.

Read-only. It writes nothing, needs no model and no Redis, and runs against the
database in `.env`, so a host shell will do.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from dotenv import load_dotenv
from sqlalchemy.exc import ProgrammingError

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

load_dotenv()

# After load_dotenv(): importing the backend reads the environment.
from backend.db import models as db_models  # noqa: E402
from backend.db.session import session_scope  # noqa: E402
from backend.logging_config import configure_logging  # noqa: E402

logger = logging.getLogger("inspect_pressure_segments")

# How much of an utterance to show in the transcript listing. Long enough to
# tell an objection from an acknowledgement, short enough that a call fits on a
# screen.
_EXCERPT = 90


class _Row:
    """One Session, reduced to what this script reports about it."""

    # pylint: disable=too-few-public-methods  # a record, printed and discarded
    # pylint: disable=too-many-instance-attributes  # one field per printed column

    def __init__(self, session: db_models.Session) -> None:
        turns = sorted(session.turns, key=lambda t: t.seq_index)
        self.extern_id = str(session.extern_id)
        self.scenario = session.scenario.title
        self.persona = session.persona.name
        self.started_at = session.started_at
        self.has_feedback = session.feedback is not None
        self.persona_turns = [t for t in turns if t.speaker == db_models.SPEAKER_PERSONA]
        self.pressed = [t for t in self.persona_turns if t.pressed]
        # NULL on every Persona row means nobody has judged this call: no
        # wrap-up yet, a failed one, or a call from before ADR 0081. That is a
        # different state from "judged, and nothing was pressing", and reading
        # the two as one is how a broken model call would look like a series of
        # calm conversations.
        self.judged = any(t.pressed is not None for t in self.persona_turns)
        # Without these there is nothing left to measure, whatever the wrap-up
        # marks: the audio is discarded when the call ends (ADR 0048).
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
        """Share of the partner's utterances marked as pressing."""
        if not self.persona_turns or not self.judged:
            return None
        return len(self.pressed) / len(self.persona_turns)

    @property
    def verdict(self) -> str:
        """What to make of this row, in one word that can be grepped for.

        A ladder of distinct states rather than a chain of conditions: each
        arm is a different thing to do about the call, and collapsing two of
        them would hide the difference between "nobody pushed back" and
        "nothing judged it", which is the whole point of the script.
        """
        # pylint: disable=too-many-return-statements  # one per state, see above
        if not self.has_facts:
            return "no-facts"       # recorded before ADR 0081; nothing to measure
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
    """One call, with the marked lines pointed at.

    The trainee's answer is shown under the line it answers, because that is the
    utterance whose figures land in the pressing stretch -- the thing to sanity
    check is not only "was this demanding" but "is the answer under it the one
    that should be measured as spoken under pressure".
    """
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
        # A single `%`, not a doubled one: logging only escapes when it is given
        # arguments to format with, and this line has none.
        logger.info(
            "Nahe 0% oder nahe 100% ist das Warnzeichen: Dann vergleicht die Anzeige "
            "zwei Abschnitte, die keine zwei sind."
        )


def main() -> None:
    """Print the table, optionally the transcripts, then the summary."""
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
        # Almost always the same thing on a first run: the database is a
        # migration behind, because the app applies them at startup and has not
        # been restarted since this feature landed. Worth naming, rather than
        # handing somebody a stack trace for a one-line answer.
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
    # One Session asked for by id is always shown in full: somebody naming an id
    # is looking at that call, not counting it.
    if args.transcript or args.session:
        for row in rows:
            _transcript(row)
    _summary(rows)


if __name__ == "__main__":
    main()
