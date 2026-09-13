"""The Scenario's briefing for the trainee

Revision ID: c8d1f3a67b40
Revises: dc5b4557e6b1

`scenario.briefing` (ADR 0054): the display text addressed to the trainee --
role, room for manoeuvre, what counts as a good outcome -- beside the four
prompt fields that brief the caller.

Hand-written for the reason CLAUDE.md gives, and the same one
`d3b8f1a05c67` gives: autogenerate emits a NOT NULL column with no backfill,
which fails on a table that already holds the seeded library. Added nullable,
backfilled, then tightened.

Backfilled with the empty string rather than from another column: there is no
column to derive it from -- the four case fields are written from the caller's
side and would address the wrong person -- and empty is a legitimate value here,
meaning a Scenario that briefs nobody, which is where every row stood before
this revision. The seed corrects the built-ins on the next start; an authored
row keeps its empty briefing until its author fills it in.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c8d1f3a67b40"
down_revision: Union[str, None] = "dc5b4557e6b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("scenario", sa.Column("briefing", sa.Text(), nullable=True))
    op.execute("UPDATE scenario SET briefing = '' WHERE briefing IS NULL")
    op.alter_column("scenario", "briefing", existing_type=sa.Text(), nullable=False)


def downgrade() -> None:
    op.drop_column("scenario", "briefing")
