"""The training focus a User has picked, and the catalogue it comes from
(F-61, ADR 0074).

The single place the `focus_goal`, `focus_selection` and `focus_selection_goal`
tables are read and written — `backend/library.py`'s role for the Scenario
library, and for the same reason: the scoping rule is one rule, and a second
query somewhere else is how it comes to hold in one place and not the other.

Every read and write here is scoped by the caller's own `sub`. The client never
supplies a subject, so there is no form of these requests that is about somebody
else and none to authorise or refuse (ADR 0031/0064).

A selection is a *setting*, not training data: it says what a User wants to work
on, not what they said in a call. Consent (ADR 0066) covers the storage of
Sessions, so no consent guard sits on this path, and `backend/deletion.py` does
not remove a selection when Sessions go — deleting your trainings must not
silently reset the goals you picked. `retention_preference` is the same kind of
row and is treated the same way.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session as DbSession

from backend.db import models as db_models
from backend.db.seed_data import FOCUS_GROUP_NAMES

logger = logging.getLogger(__name__)

# How many goals one subject may focus on at once.
#
# Five, and the number is the whole of the rule: a focus that covers everything
# is not a focus, and a limit the interface enforces but the API does not is not
# a limit. The client reads it from `/api/focus` rather than carrying its own
# copy, so the two cannot disagree (the same reason ADR 0063 gives for the
# editor's field limits).
MAX_GOALS = 5


@dataclass(frozen=True)
class Goal:
    """One entry of the catalogue, as the interface needs it."""

    key: str
    title: str
    caption: str
    info: str
    group: str
    evidence: str


@dataclass(frozen=True)
class Selection:
    """What one subject has decided, if anything.

    `decided` and an empty `keys` are different answers to different questions:
    a subject who continued without a focus has decided, and must not be asked
    again. Only a subject with no row at all is undecided.
    """

    decided: bool
    decided_at: datetime | None
    keys: tuple[str, ...]

    @property
    def decision_required(self) -> bool:
        """True while the interface still has to ask."""
        return not self.decided


def groups() -> list[dict[str, str]]:
    """The catalogue's headings, in catalogue order.

    Served alongside the goals rather than held in the frontend: the goal text
    already comes from the database, and a heading kept somewhere else is a
    second place to edit when the catalogue changes.
    """
    return [{"key": key, "name": name} for key, name in FOCUS_GROUP_NAMES.items()]


def list_goals(db: DbSession) -> list[Goal]:
    """The selectable catalogue, in display order.

    Only active rows. A retired goal stays in the table because selections
    reference it, but it must not be offered again.
    """
    rows = (
        db.query(db_models.FocusGoal)
        .filter_by(active=True)
        .order_by(db_models.FocusGoal.position)
        .all()
    )
    return [
        Goal(
            key=row.key,
            title=row.title,
            caption=row.caption,
            info=row.info,
            group=row.group_key,
            evidence=row.evidence,
        )
        for row in rows
    ]


def selection(db: DbSession, subject_id: str) -> Selection:
    """The subject's current focus, or an undecided state if they have none."""
    row = (
        db.query(db_models.FocusSelection)
        .filter_by(subject_id=subject_id)
        .one_or_none()
    )
    if row is None:
        return Selection(decided=False, decided_at=None, keys=())
    return Selection(
        decided=True,
        decided_at=row.decided_at,
        keys=_selected_keys(db, row.selection_id),
    )


class UnknownGoal(ValueError):
    """A key the catalogue does not offer. A client bug, not a user error."""


class TooManyGoals(ValueError):
    """More goals than MAX_GOALS. Enforced here, not only in the interface."""


def set_selection(db: DbSession, subject_id: str, keys: list[str]) -> Selection:
    """Replace the subject's focus with `keys`. An empty list is "no focus".

    Replaced rather than merged: the selection is a set of at most five, and the
    client always sends the whole of it, so a partial update would need a second
    call to remove anything and could leave the row in a state nobody chose.

    Raises UnknownGoal / TooManyGoals, which the route turns into a 400 — both
    mean the request was wrong, and silently dropping the surplus would store a
    focus the user did not pick.
    """
    wanted = list(dict.fromkeys(keys))  # de-duplicated, order preserved
    if len(wanted) > MAX_GOALS:
        raise TooManyGoals(f"at most {MAX_GOALS} goals may be selected")

    rows: dict[str, db_models.FocusGoal] = {}
    if wanted:
        # `IN ()` is not valid SQL, hence the guard rather than an unconditional
        # query -- the same reason api/account.py's _count() has one.
        rows = {
            row.key: row
            for row in db.query(db_models.FocusGoal).filter(
                db_models.FocusGoal.key.in_(wanted),
                db_models.FocusGoal.active.is_(True),
            )
        }
    missing = [key for key in wanted if key not in rows]
    if missing:
        raise UnknownGoal(f"unknown focus goal(s): {', '.join(missing)}")

    now = datetime.now(UTC)
    record = (
        db.query(db_models.FocusSelection)
        .filter_by(subject_id=subject_id)
        .one_or_none()
    )
    if record is None:
        record = db_models.FocusSelection(
            subject_id=subject_id, decided_at=now, updated_at=now
        )
        db.add(record)
        db.flush()  # the goal rows below need the selection's id
    else:
        # `decided_at` is deliberately untouched: it records when the question
        # was first answered, and a later change does not unmake that.
        record.updated_at = now
        db.query(db_models.FocusSelectionGoal).filter_by(
            selection_id=record.selection_id
        ).delete(synchronize_session=False)

    for key in wanted:
        db.add(db_models.FocusSelectionGoal(
            selection_id=record.selection_id,
            focus_goal_id=rows[key].focus_goal_id,
        ))
    db.flush()  # so a caller in the same transaction reads the new set back

    logger.info("Focus selection stored (%d goal(s))", len(wanted))
    return Selection(
        decided=True,
        decided_at=record.decided_at,
        keys=_selected_keys(db, record.selection_id),
    )


def _selected_keys(db: DbSession, selection_id: int) -> tuple[str, ...]:
    """The selected keys in catalogue order.

    Ordered by the catalogue and not by when they were picked: the selection is
    a set of at most five and nothing about it is ranked, so an order of its own
    would suggest a priority the user never expressed.
    """
    rows = (
        db.query(db_models.FocusGoal.key)
        .join(
            db_models.FocusSelectionGoal,
            db_models.FocusSelectionGoal.focus_goal_id == db_models.FocusGoal.focus_goal_id,
        )
        .filter(db_models.FocusSelectionGoal.selection_id == selection_id)
        .order_by(db_models.FocusGoal.position)
        .all()
    )
    return tuple(key for (key,) in rows)
