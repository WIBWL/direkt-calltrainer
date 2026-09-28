"""Training role and call types on the focus selection

Revision ID: d4e7a2c91b36
Revises: a91c5f70d8e3

What a User says about their work, beside the goals they picked (F-62): one
role, and the kinds of call they take. The call types use the vocabulary of
`scenario.category`, which is what lets them steer the Scenario recommendations.

`role` is nullable and not backfilled: everyone who answered before the question
existed simply has none.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d4e7a2c91b36"
down_revision: Union[str, None] = "a91c5f70d8e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("focus_selection", sa.Column("role", sa.String(length=20), nullable=True))
    # CHECKs by hand: autogenerate does not detect them. The bare name, because
    # op.create_check_constraint applies the naming convention itself.
    op.create_check_constraint(
        "role_valid", "focus_selection",
        "role IN ('sales', 'service', 'support', 'consulting', 'other')",
    )

    op.create_table(
        "focus_selection_category",
        sa.Column("selection_category_id", sa.Integer(), nullable=False),
        sa.Column("selection_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.CheckConstraint(
            "category IN ('operations', 'requirements', 'pricing', 'closing')",
            name=op.f("ck_focus_selection_category_category_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["selection_id"], ["focus_selection.selection_id"],
            name=op.f("fk_focus_selection_category_selection_id_focus_selection"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "selection_category_id", name=op.f("pk_focus_selection_category")
        ),
        sa.UniqueConstraint(
            "selection_id", "category",
            name=op.f("uq_focus_selection_category_selection_id"),
        ),
    )
    # Every foreign-key column is indexed (ADR 0052).
    op.create_index(
        op.f("ix_focus_selection_category_selection_id"),
        "focus_selection_category", ["selection_id"], unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_focus_selection_category_selection_id"),
        table_name="focus_selection_category",
    )
    op.drop_table("focus_selection_category")
    op.drop_constraint("role_valid", "focus_selection", type_="check")
    op.drop_column("focus_selection", "role")
