"""Interrupted flag on turn

Revision ID: e7b3d9c1a542
Revises: c8a1f60d34be

A Persona utterance that was cut back to the part the user actually heard
(ADR 0035) has so far been recognisable only by the "... [unterbrochen]" marker
appended to its transcript. That marker is a display decision. The interruption
classification of F-51 computes on it, and computing on a rendering choice
means the figure changes the day somebody rewords the marker.

Additive: one boolean, NOT NULL with a server-side default of false, so the
column can be added to a populated table in one statement.

The backfill reads the marker exactly once, here, and is safe because it is
derived from data already present rather than invented: every row carrying the
marker was written by `utterances()` for an interrupted reply and by nothing
else. From now on `persistence.py` writes the flag and the marker from the same
in-memory field.

`server_default` is dropped again afterwards, so the column follows the
convention the rest of the schema keeps (Python-side defaults only, see
models.py) and a row inserted by hand has to name it.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e7b3d9c1a542"
down_revision: Union[str, None] = "c8a1f60d34be"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MARKER = "%[unterbrochen]%"


def upgrade() -> None:
    op.add_column(
        "turn",
        sa.Column("interrupted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(
        sa.text(
            "UPDATE turn SET interrupted = true "
            "WHERE speaker = 'persona' AND transcript LIKE :marker"
        ).bindparams(marker=MARKER)
    )
    op.alter_column("turn", "interrupted", server_default=None)


def downgrade() -> None:
    op.drop_column("turn", "interrupted")
