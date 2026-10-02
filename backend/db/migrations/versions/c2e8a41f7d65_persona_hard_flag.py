"""Persona gains the one difficulty distinction the turn loop reads

Revision ID: c2e8a41f7d65
Revises: 5d9a3f7c21e8

`persona.hard` selects the anti-repeat nudge that does not offer giving ground
(`nudges.for_turn`). Migration 5d9a3f7c21e8 dropped the `difficulty` scale
because nothing read it; this is the single distinction something now does.
Every existing row is backfilled False; the seed sets the hard ones on the
next start. The server default exists only to backfill and is removed again,
as column defaults are Python-side in this schema.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c2e8a41f7d65"
down_revision: Union[str, None] = "5d9a3f7c21e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "persona",
        sa.Column("hard", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("persona", "hard", server_default=None)


def downgrade() -> None:
    op.drop_column("persona", "hard")
