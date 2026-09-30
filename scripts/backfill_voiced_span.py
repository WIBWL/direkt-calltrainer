"""Correct the figures the VAD's padding distorted, for Sessions stored before ADR 0108.

    python scripts/backfill_voiced_span.py            # show what would change
    python scripts/backfill_voiced_span.py --apply    # write it

Redeanteil and Redefluss are recomputed **exactly** from figures already stored:
the user's phonation (Redefluss' or Sprechtempo's detail) plus the total of the
pauses inside it is the span from first sound to last, which is what both divide
by now. Redeanteil over a pressing stretch and the rest (ADR 0081) is recomputed
from the Turns' stored facts, the way the wrap-up measured it.

The Reaktionszeit is corrected **approximately**, and only where the Turns carry
their loudness curve (ADR 0081, stored from 2026-09-11): the first sound is read
off the curve's first audible sample, 100 ms apart, so each gap is right to about
a tenth of a second instead of 0.8 s short. Its `at_ms` stay on the transcript's
offsets, which this script does not move. Older Sessions keep their figure and
are counted at the end.

A figure the new rule withholds -- a Redeanteil over a recording without
silence (ADR 0085) -- is deleted rather than left wrong. Uses `.env`'s database
(no Redis, no model). Idempotent: a second run after `--apply` changes nothing."""

# pylint: disable=duplicate-code
# The sys.path preamble and the main()/__name__ guard cannot move into
# `_backfill_cli`: the preamble must run before that import.


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
from sqlalchemy.orm import Session as DbSession  # noqa: E402

from backend.db import models as db_models  # noqa: E402
from backend.db.session import session_scope  # noqa: E402
from backend.feedback import metrics, rows, segments, stored  # noqa: E402
from backend.feedback.calls import Reaction, conversation  # noqa: E402
from backend.feedback.metrics import Measurement  # noqa: E402
from scripts import _backfill_cli  # noqa: E402

logger = logging.getLogger("backfill_voiced_span")

# The stored loudness curve's spacing (acoustics._SAMPLE_INTERVAL_MS), which is
# the resolution the first sound can be read off it at.
_CURVE_STEP_MS = 100

_MS_PER_MINUTE = 60_000


class _Tally:  # pylint: disable=too-few-public-methods  # a counter, not a model
    """What the run could not correct, for the closing report."""

    def __init__(self) -> None:
        self.reaction_uncorrectable = 0


def _whole_call(session: db_models.Session, by_id: dict[int, str]) -> dict[str, db_models.Measurement]:
    """The whole call's rows by metric key."""
    return {
        by_id[m.metric_type_id]: m for m in stored.whole_call(session) if m.metric_type_id in by_id
    }


def _phonation_ms(found: dict[str, db_models.Measurement]) -> int | None:
    """The user's phonation over the call, from whichever row stored it.

    Redefluss' detail first (exact), then Sprechtempo's (from 2026-09-20), then
    Sprechtempo's division undone: words over phonation, stored to four
    decimals, which gives the milliseconds back to well under one. Either row
    is only stored when every Turn was measured and silence was found -- the
    rule Redeanteil follows now as well -- so None also means "withheld"."""
    share = found.get("phonation_share")
    if share is not None and (share.detail_json or {}).get("phonation_ms"):
        return int(share.detail_json["phonation_ms"])
    pace = found.get("pace")
    if pace is None or not pace.value:
        return None
    detail = pace.detail_json or {}
    if detail.get("phonation_ms"):
        return int(detail["phonation_ms"])
    word_count = found.get("word_count")
    words = detail.get("words") or (word_count.value if word_count is not None else None)
    if not words:
        return None
    return round(float(words) * _MS_PER_MINUTE / float(pace.value))


def _voiced_ms(found: dict[str, db_models.Measurement], phonation: int) -> int:
    """Phonation plus the pauses inside it: the span from first sound to last
    (`Conversation.user_voiced_ms`). No `pauses` row next to a phonation figure
    means there were none -- both rest on the same split into speech and silence."""
    pauses = found.get("pauses")
    total_s = (pauses.detail_json or {}).get("total_s", 0) if pauses is not None else 0
    return phonation + round(float(total_s) * 1000)


def _write(row: db_models.Measurement, measurement: Measurement) -> None:
    """Rewrite one row in place, marked as reconstructed (`rows.measurements`)."""
    row.value = Decimal(f"{measurement.value:.{rows.VALUE_SCALE}f}")
    row.detail_json = (measurement.detail or {}) | {"backfilled": True}


def _talk(
    db: DbSession, found: dict[str, db_models.Measurement], voiced: int | None, apply: bool
) -> list[str]:
    """Redeanteil over the whole call. Returns what changed, in words."""
    talk = found.get("talk_share")
    if talk is None:
        return []
    if voiced is None:
        # Deleted only where the call positively found no silence: words were
        # counted and every Turn measured (a Redeanteil was stored at all), yet
        # no Sprechtempo -- the one reason left for it to be withheld. A figure
        # this script merely cannot place stays.
        if "word_count" not in found or "pace" in found:
            return []
        if apply:
            db.delete(talk)
        return [f"Redeanteil {float(talk.value):.1f} % entfällt (keine Stille gefunden)"]
    persona_ms = (talk.detail_json or {}).get("persona_ms")
    if persona_ms is None or (talk.detail_json or {}).get("user_ms") == voiced:
        return []
    new = metrics.talk_share_measurement(voiced, int(persona_ms))
    if new is None:
        return []
    if apply:
        _write(talk, new)
    return [f"Redeanteil {float(talk.value):.1f} % -> {new.value:.1f} %"]


def _flow(
    found: dict[str, db_models.Measurement], phonation: int | None, voiced: int | None, apply: bool
) -> list[str]:
    """Redefluss over the whole call. Returns what changed, in words."""
    flow = found.get("phonation_share")
    if flow is None or not phonation or not voiced:
        return []
    if (flow.detail_json or {}).get("voiced_ms") == voiced:
        return []
    new = metrics.phonation_share_measurement(phonation, voiced)
    if new is None:
        return []
    if apply:
        _write(flow, new)
    return [f"Redefluss {float(flow.value):.1f} % -> {new.value:.1f} %"]


def _segment_talk(
    db: DbSession, session: db_models.Session, talk_id: int, apply: bool
) -> list[str]:
    """Redeanteil over the pressing stretches and the rest, measured again from
    the Turns' stored facts by the wrap-up's own function."""
    stored_rows = {
        m.segment: m for m in session.measurements
        if m.metric_type_id == talk_id and m.segment != db_models.SEGMENT_CALL
    }
    if not stored_rows:
        return []
    pressed = {row.turn_id for row in session.turns if row.pressed}
    measured = segments.measure_segments(session, pressed)

    changes: list[str] = []
    for segment, row in stored_rows.items():
        new = next((m for m in measured.get(segment, []) if m.key == "talk_share"), None)
        if new is None:
            changes.append(f"Redeanteil ({segment}) {float(row.value):.1f} % entfällt")
            if apply:
                db.delete(row)
        elif (row.detail_json or {}).get("user_ms") != (new.detail or {}).get("user_ms"):
            changes.append(f"Redeanteil ({segment}) {float(row.value):.1f} % -> {new.value:.1f} %")
            if apply:
                _write(row, new)
    return changes


def _first_sound_ms(curve: list[float | None]) -> int:
    """Where the first audible sample of a stored loudness curve lies, taken as
    the middle of the step it was first heard in."""
    first = next((index for index, value in enumerate(curve) if value is not None), None)
    if first is None:
        return 0
    return max(0, first * _CURVE_STEP_MS - _CURVE_STEP_MS // 2)


def _reaction(
    session: db_models.Session, row: db_models.Measurement, tally: _Tally, apply: bool
) -> list[str]:
    """The reaction time, re-measured to an estimate of each reply's first sound."""
    if (row.detail_json or {}).get("measured_to"):
        return []  # measured to the first sound already, live or by an earlier run
    exchanges = stored.exchanges(session)
    if not any(stored_row.acoustics_json for _, stored_row in exchanges):
        tally.reaction_uncorrectable += 1
        return []

    # Shift each measured reply to its first sound, remembering where the
    # transcript has it: the page finds the reply by that offset.
    transcript_offset: dict[int, int] = {}
    for turn, stored_row in exchanges:
        measured = stored_row.speaker == db_models.SPEAKER_USER and bool(stored_row.acoustics_json)
        if not measured or not turn.user_acoustics_complete or turn.user_offset_ms is None:
            continue
        shifted = turn.user_offset_ms + _first_sound_ms(turn.loudness_db)
        transcript_offset[shifted] = turn.user_offset_ms
        turn.user_offset_ms = shifted

    call = conversation([turn for turn, _ in exchanges])
    reactions = [
        Reaction(transcript_offset.get(reaction.at_ms, reaction.at_ms), reaction.gap_ms)
        for reaction in call.reactions
    ]
    new = metrics.reaction_time_measurement(reactions)
    if new is None:
        return []
    if apply:
        _write(row, Measurement(new.key, new.value, (new.detail or {}) | {"first_sound_estimated": True}))
    return [f"Reaktionszeit {float(row.value):.2f} s -> {new.value:.2f} s (geschätzt)"]


def backfill(apply: bool) -> int:
    """Correct every stored Session that needs it. Returns how many changed."""
    changed = 0
    tally = _Tally()
    with session_scope() as db:
        by_key = _backfill_cli.metric_ids(db, logger, "talk_share", "phonation_share", "reaction_time")
        if by_key is None:
            return 0
        by_id = {v: k for k, v in by_key.items()}

        for session in _backfill_cli.each_session(db):
            found = _whole_call(session, by_id)
            phonation = _phonation_ms(found)
            voiced = _voiced_ms(found, phonation) if phonation else None
            changes = _talk(db, found, voiced, apply) + _flow(found, phonation, voiced, apply)
            changes += _segment_talk(db, session, by_key["talk_share"], apply)
            if "reaction_time" in found:
                changes += _reaction(session, found["reaction_time"], tally, apply)
            if not changes:
                continue
            logger.info("Session %s: %s", session.extern_id, "; ".join(changes))
            changed += 1

    if tally.reaction_uncorrectable:
        logger.info(
            "%d Session(s) ohne gespeicherte Lautstärkekurve je Beitrag: Reaktionszeit "
            "bleibt, wie sie ist (vor 2026-09-11 gespeichert)",
            tally.reaction_uncorrectable,
        )
    return changed


def main() -> int:
    """CLI entry point. Returns the process exit code."""
    return _backfill_cli.run(backfill, __doc__.splitlines()[0], logger)


if __name__ == "__main__":
    raise SystemExit(main())
