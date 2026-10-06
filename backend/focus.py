"""The focus catalogue and selections (F-62, ADR 0076), scoped by `sub`. A setting:
no consent guard, and deletion never touches it."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session as DbSession

from shared.db import models as db_models
from shared.db.seed_data import FOCUS_GROUP_NAMES, TRAINING_ROLE_CATALOGUE
from backend import consent

logger = logging.getLogger(__name__)

# Served via /api/focus so the client never keeps its own copy.
MAX_GOALS = 5


@dataclass(frozen=True)
class Goal:
    key: str
    title: str
    caption: str
    info: str
    group: str
    evidence: str


@dataclass(frozen=True)
class Selection:
    """`decided` with no keys means "no focus" and is never asked again."""

    decided: bool
    decided_at: datetime | None
    keys: tuple[str, ...]
    # Both optional; categories use `scenario.category` values.
    role: str | None = None
    categories: tuple[str, ...] = ()

    @property
    def decision_required(self) -> bool:
        return not self.decided


def groups() -> list[dict[str, str]]:
    """Served, so a catalogue change is edited in one place."""
    return [{"key": key, "name": name} for key, name in FOCUS_GROUP_NAMES.items()]


def roles() -> list[dict]:
    return TRAINING_ROLE_CATALOGUE


def list_goals(db: DbSession) -> list[Goal]:
    """Active rows only: retired goals stay for the selections that name them."""
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
    row = (
        db.query(db_models.FocusSelection)
        .filter_by(subject_id=subject_id)
        .one_or_none()
    )
    if row is None:
        return Selection(decided=False, decided_at=None, keys=())
    return _as_selection(db, row)


class UnknownGoal(ValueError):
    """A client bug, not a user error."""


class TooManyGoals(ValueError):
    """More than MAX_GOALS."""


class UnknownChoice(ValueError):
    """A role or call type outside its vocabulary."""


def _checked(
    db: DbSession,
    keys: list[str],
    role: str | None,
    categories: list[str] | None,
) -> tuple[list[str], dict[str, db_models.FocusGoal], list[str]]:
    """De-duplicated goal keys, their rows, and de-duplicated call types; or a refusal."""
    wanted = list(dict.fromkeys(keys))
    if len(wanted) > MAX_GOALS:
        raise TooManyGoals(f"at most {MAX_GOALS} goals may be selected")

    rows: dict[str, db_models.FocusGoal] = {}
    if wanted:
        # `IN ()` is not valid SQL.
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

    if role is not None and role not in db_models.TRAINING_ROLES:
        raise UnknownChoice(f"unknown role: {role}")

    kinds = list(dict.fromkeys(categories or ()))
    strange = [kind for kind in kinds if kind not in db_models.SCENARIO_CATEGORIES]
    if strange:
        # Only the first few: echoing all of them let a huge request amplify its 400.
        more = f" (and {len(strange) - 3} more)" if len(strange) > 3 else ""
        raise UnknownChoice(f"unknown call type(s): {', '.join(strange[:3])}{more}")

    return wanted, rows, kinds


def set_selection(
    db: DbSession,
    subject_id: str,
    keys: list[str],
    role: str | None = None,
    categories: list[str] | None = None,
) -> Selection:
    """Replaces everything; raises rather than truncating."""
    wanted, rows, kinds = _checked(db, keys, role, categories)

    now = datetime.now(UTC)
    # The consent lock: a double press would otherwise insert twice and report
    # a failed save that worked.
    consent.lock_subject(db, subject_id)
    record = (
        db.query(db_models.FocusSelection)
        .filter_by(subject_id=subject_id)
        .one_or_none()
    )
    if record is None:
        record = db_models.FocusSelection(
            subject_id=subject_id, decided_at=now, updated_at=now, role=role
        )
        db.add(record)
        db.flush()
    else:
        # `decided_at` keeps the first answer.
        record.updated_at = now
        record.role = role
        for table in (db_models.FocusSelectionGoal, db_models.FocusSelectionCategory):
            db.query(table).filter_by(
                selection_id=record.selection_id
            ).delete(synchronize_session=False)

    for key in wanted:
        db.add(db_models.FocusSelectionGoal(
            selection_id=record.selection_id,
            focus_goal_id=rows[key].focus_goal_id,
        ))
    for kind in kinds:
        db.add(db_models.FocusSelectionCategory(
            selection_id=record.selection_id, category=kind,
        ))
    db.flush()

    logger.info(
        "Focus selection stored (%d goal(s), %d call type(s))", len(wanted), len(kinds)
    )
    return _as_selection(db, record)


def _as_selection(db: DbSession, row: db_models.FocusSelection) -> Selection:
    stored = {
        kind for (kind,) in db.query(db_models.FocusSelectionCategory.category)
        .filter_by(selection_id=row.selection_id)
    }
    return Selection(
        decided=True,
        decided_at=row.decided_at,
        keys=_selected_keys(db, row.selection_id),
        role=row.role,
        # Vocabulary order, like the goals.
        categories=tuple(kind for kind in db_models.SCENARIO_CATEGORIES if kind in stored),
    )


def _selected_keys(db: DbSession, selection_id: int) -> tuple[str, ...]:
    """Catalogue order: pick order would suggest a ranking the user never gave."""
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
