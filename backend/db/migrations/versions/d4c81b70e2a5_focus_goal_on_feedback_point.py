"""Which focus goal a feedback point is about

Revision ID: d4c81b70e2a5
Revises: b6e2d914f70a

Stage 2 of the dashboard (docs/dashboard-konzept.md, section D). The wrap-up
already writes points of two kinds; what it could not do is say what a point
was *about*, so nothing could be counted across a user's trainings and the
recurring-strengths block stood on the page as a labelled placeholder.

A foreign key into the reference table rather than a text column: two spellings
of the same weakness would otherwise count as two, and the aggregation has to be
deterministic.

No ondelete. `focus_goal` is a reference table and stays undeletable while
anything points at it, exactly as `feedback_point.metric_type_id` does. Retired
goals are deactivated, never deleted (ADR 0076), so a point keeps its meaning
after its goal leaves the catalogue.

Indexed, per ADR 0052: every foreign-key column is, and this one is also what
the dashboard groups by.

Added nullable and left unfilled. Wrap-ups written before this came from a
prompt that was never asked for a goal, and guessing one now from the text
would be inventing the data the block exists to count. NULL there means "not
assigned", and the block leaves such a point out of its counts rather than
filing it under a goal nobody chose. Re-queueing a wrap-up
(`scripts/requeue_feedback.py`) does produce the assignment.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d4c81b70e2a5"
down_revision: Union[str, None] = "b6e2d914f70a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "feedback_point", sa.Column("focus_goal_id", sa.Integer(), nullable=True)
    )
    op.create_index(
        op.f("ix_feedback_point_focus_goal_id"),
        "feedback_point",
        ["focus_goal_id"],
    )
    op.create_foreign_key(
        op.f("fk_feedback_point_focus_goal_id_focus_goal"),
        "feedback_point",
        "focus_goal",
        ["focus_goal_id"],
        ["focus_goal_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_feedback_point_focus_goal_id_focus_goal"),
        "feedback_point",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_feedback_point_focus_goal_id"), table_name="feedback_point")
    op.drop_column("feedback_point", "focus_goal_id")
