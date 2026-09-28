"""Unheard text on turn

Revision ID: a91c5f70d8e3
Revises: e7b3d9c1a542

What the Persona had been about to say when the user cut in (F-51). The
wrap-up's interruption drill-down shows the cut-off line and this beside it, so
the user can see not only that they interrupted but what they interrupted.

Nullable, and it stays NULL on every row written before this column existed:
the words were discarded at the time (ADR 0035 trims the reply to the heard part
and the remainder was dropped on the floor), so there is nothing to backfill
from. The drill-down says so for those Sessions rather than showing an empty
line.

Kept apart from `transcript` on purpose. That column is what was said in the
call; this is what was not. Merging them would put words into a transcript that
nobody heard, which is the one thing ADR 0035 is careful about.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a91c5f70d8e3"
down_revision: Union[str, None] = "e7b3d9c1a542"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("turn", sa.Column("unheard_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("turn", "unheard_text")
