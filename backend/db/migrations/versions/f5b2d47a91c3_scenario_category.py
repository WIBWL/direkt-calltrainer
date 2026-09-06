"""Category on scenario

Revision ID: f5b2d47a91c3
Revises: e4a9c07b2f31

ADR 0064: the F-03 call context a Scenario belongs to, and the vocabulary the
library's category slider filters on. Not a return of the `scenario_type` that
`e4a9c07b2f31` dropped: that one was free text with no vocabulary and no
reader, and this one is a CHECK-enforced closed list that the selection screen
reads.

Nullable, with no backfill. An authored row written before this column existed
has no category, and picking one for its author would file it under a context
nobody chose; the seeded built-ins all carry one because the seed sets it. A
`col IN (...)` CHECK passes for NULL, so the constraint and the nullability sit
together without a second clause.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f5b2d47a91c3"
down_revision: Union[str, None] = "e4a9c07b2f31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("scenario", sa.Column("category", sa.String(length=20), nullable=True))
    # Autogenerate does not detect CHECK constraints; written by hand, and with
    # the bare name because op.create_check_constraint applies the naming
    # convention itself.
    op.create_check_constraint(
        "category_valid",
        "scenario",
        "category IN ('operations', 'requirements', 'pricing', 'closing')",
    )


def downgrade() -> None:
    op.drop_constraint("category_valid", "scenario", type_="check")
    op.drop_column("scenario", "category")
