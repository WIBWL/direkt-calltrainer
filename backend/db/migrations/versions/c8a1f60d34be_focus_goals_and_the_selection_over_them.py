"""Focus goals and the selection over them

Revision ID: c8a1f60d34be
Revises: dc5b4557e6b1

The three tables behind F-61 / ADR 0074: the shipped catalogue of training
focuses, the fact that one subject has answered the question, and the at most
five goals they picked.

Three tables and not one, for two reasons. "Picked no focus" and "was never
asked" are different states -- the first must never re-open the first-run
dialog, the second always must -- so the decision needs a row of its own that
exists independently of any goal. And the goals themselves are a catalogue that
selections reference, which is what makes a retired goal deactivatable instead
of deletable, exactly as `persona` and `scenario` are (ADR 0041).

`focus_selection.subject_id` carries no foreign key, for the same reason
`session.subject_id` does not (ADR 0031): identity lives in Keycloak and there
is no local User table to point at. It is unique rather than merely indexed --
a subject has one current focus, and two rows would make the answer depend on
which was read first.

The ownership edge cascades (`focus_selection_goal` -> `focus_selection`), the
reference edge does not (`focus_selection_goal` -> `focus_goal`): a FocusGoal
with selections behind it must not be deletable at all, which is the same split
ADR 0026/0052 apply everywhere else.

Purely additive: three new tables, no column touched on an existing one, so this
runs on a populated database without rewriting a row. Constraint and index names
are passed through op.f() so they match the convention on Base.metadata
(ADR 0053).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c8a1f60d34be"
down_revision: Union[str, None] = "dc5b4557e6b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "focus_goal",
        sa.Column("focus_goal_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("caption", sa.String(length=240), nullable=False),
        sa.Column("info", sa.Text(), nullable=False),
        sa.Column("group_key", sa.String(length=20), nullable=False),
        sa.Column("evidence", sa.String(length=20), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        # Written by hand: autogenerate does not detect CHECK constraints
        # (ADR 0027, CLAUDE.md). Both vocabularies are closed and enforced at
        # the database rather than by a Postgres ENUM (ADR 0053).
        sa.CheckConstraint(
            "group_key IN ('paraverbal', 'phases', 'impact', 'habit')",
            name=op.f("ck_focus_goal_group_key_valid"),
        ),
        sa.CheckConstraint(
            "evidence IN ('measured', 'mixed', 'interpretive')",
            name=op.f("ck_focus_goal_evidence_valid"),
        ),
        sa.PrimaryKeyConstraint("focus_goal_id", name=op.f("pk_focus_goal")),
        sa.UniqueConstraint("key", name=op.f("uq_focus_goal_key")),
    )

    op.create_table(
        "focus_selection",
        sa.Column("selection_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.String(length=64), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("selection_id", name=op.f("pk_focus_selection")),
        sa.UniqueConstraint("subject_id", name=op.f("uq_focus_selection_subject_id")),
    )

    op.create_table(
        "focus_selection_goal",
        sa.Column("selection_goal_id", sa.Integer(), nullable=False),
        sa.Column("selection_id", sa.Integer(), nullable=False),
        sa.Column("focus_goal_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["focus_goal_id"], ["focus_goal.focus_goal_id"],
            name=op.f("fk_focus_selection_goal_focus_goal_id_focus_goal"),
        ),
        sa.ForeignKeyConstraint(
            ["selection_id"], ["focus_selection.selection_id"],
            name=op.f("fk_focus_selection_goal_selection_id_focus_selection"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "selection_goal_id", name=op.f("pk_focus_selection_goal")
        ),
        # The same goal twice would let a subject spend two of their five slots
        # on one goal, and the count is the whole of the limit.
        sa.UniqueConstraint(
            "selection_id", "focus_goal_id",
            name=op.f("uq_focus_selection_goal_selection_id"),
        ),
    )
    # Every foreign-key column is indexed (ADR 0052).
    op.create_index(
        op.f("ix_focus_selection_goal_focus_goal_id"),
        "focus_selection_goal", ["focus_goal_id"], unique=False,
    )
    op.create_index(
        op.f("ix_focus_selection_goal_selection_id"),
        "focus_selection_goal", ["selection_id"], unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_focus_selection_goal_selection_id"), table_name="focus_selection_goal"
    )
    op.drop_index(
        op.f("ix_focus_selection_goal_focus_goal_id"), table_name="focus_selection_goal"
    )
    op.drop_table("focus_selection_goal")
    op.drop_table("focus_selection")
    op.drop_table("focus_goal")
