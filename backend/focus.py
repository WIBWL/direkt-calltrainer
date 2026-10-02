"""The training focus a User has picked, and its catalogue (F-62, ADR 0076).

The single place the `focus_goal`, `focus_selection` and `focus_selection_goal` tables
are read and written, always scoped by the caller's `sub` (ADR 0031/0064). A selection
is a *setting*: no consent guard, and `backend/deletion.py` never removes it."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session as DbSession

from backend import consent
from backend.db import models as db_models
from backend.db.seed_data import FOCUS_GROUP_NAMES, TRAINING_ROLE_CATALOGUE

logger = logging.getLogger(__name__)

# How many goals one subject may focus on at once. Enforced here, and served
# via `/api/focus` so the client never carries its own copy (as in ADR 0063).
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
    """What one subject has decided, if anything. `decided` with empty `keys`
    means "continued without a focus" and must not be asked again; only a subject
    with no row at all is undecided."""

    decided: bool
    decided_at: datetime | None
    keys: tuple[str, ...]
    # What the subject said about their work: one role, and the call types they
    # take (`scenario.category` values). Both optional.
    role: str | None = None
    categories: tuple[str, ...] = ()

    @property
    def decision_required(self) -> bool:
        """True while the interface still has to ask."""
        return not self.decided


def groups() -> list[dict[str, str]]:
    """The catalogue's headings, in catalogue order -- served rather than held in
    the frontend, so a catalogue change is edited in one place."""
    return [{"key": key, "name": name} for key, name in FOCUS_GROUP_NAMES.items()]


def roles() -> list[dict]:
    """The roles on offer, each with the call types it preselects."""
    return TRAINING_ROLE_CATALOGUE


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
    return _as_selection(db, row)


class UnknownGoal(ValueError):
    """A key the catalogue does not offer. A client bug, not a user error."""


class TooManyGoals(ValueError):
    """More goals than MAX_GOALS. Enforced here, not only in the interface."""


class UnknownChoice(ValueError):
    """A role or call type outside its vocabulary. A client bug, like UnknownGoal."""


def _checked(
    db: DbSession,
    keys: list[str],
    role: str | None,
    categories: list[str] | None,
) -> tuple[list[str], dict[str, db_models.FocusGoal], list[str]]:
    """What `set_selection` may store, or the refusal that stops it.

    Checks goals (count, existence, active), role and call types. Returns the
    de-duplicated goal keys, the goal rows and the de-duplicated call types.
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

    if role is not None and role not in db_models.TRAINING_ROLES:
        raise UnknownChoice(f"unknown role: {role}")

    kinds = list(dict.fromkeys(categories or ()))
    strange = [kind for kind in kinds if kind not in db_models.SCENARIO_CATEGORIES]
    if strange:
        # Name only the first few: the call types are not capped, and echoing
        # all of them in the 400 body let a huge request amplify its answer.
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
    """Replace the subject's focus with `keys`. An empty list is "no focus".

    Role and call types are replaced too; the client always sends the whole
    selection. Raises UnknownGoal / TooManyGoals (a 400), never truncates.
    """
    wanted, rows, kinds = _checked(db, keys, role, categories)

    now = datetime.now(UTC)
    # Same lock the consent write takes, for the same reason: `focus_selection`
    # is unique per subject and this reads before it inserts, so two requests
    # from one person -- a double press on the first-run dialog -- both find no
    # row and both insert. The loser gets an IntegrityError and the dialog
    # reports a failure for a save that worked.
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
        db.flush()  # the goal rows below need the selection's id
    else:
        # `decided_at` is deliberately untouched: it records when the question
        # was first answered, and a later change does not unmake that.
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
    db.flush()  # so a caller in the same transaction reads the new set back

    logger.info(
        "Focus selection stored (%d goal(s), %d call type(s))", len(wanted), len(kinds)
    )
    return _as_selection(db, record)


def _as_selection(db: DbSession, row: db_models.FocusSelection) -> Selection:
    """One stored selection, read back in catalogue order."""
    stored = {
        kind for (kind,) in db.query(db_models.FocusSelectionCategory.category)
        .filter_by(selection_id=row.selection_id)
    }
    return Selection(
        decided=True,
        decided_at=row.decided_at,
        keys=_selected_keys(db, row.selection_id),
        role=row.role,
        # Vocabulary order, not insertion order, for the reason _selected_keys gives.
        categories=tuple(kind for kind in db_models.SCENARIO_CATEGORIES if kind in stored),
    )


def _selected_keys(db: DbSession, selection_id: int) -> tuple[str, ...]:
    """The selected keys in catalogue order -- the selection is unranked, so
    pick order would suggest a priority the user never expressed."""
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
