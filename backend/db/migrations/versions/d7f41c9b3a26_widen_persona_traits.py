"""Persona traits as text rather than a capped column

Revision ID: d7f41c9b3a26
Revises: 3ce81b27af40

`persona.traits` was String(120). The cap was a guess, and the seed outgrew it
the moment a Persona's role was trimmed to the position alone (a442f5d) and
everything the role used to imply moved into the traits: four of the six
seeded Personas then carried 129-141 characters, provisioning died on the
first of them with `value too long for type character varying(120)`, and an
app that cannot seed answers every request with "no 'default' tenant is
seeded".

Text, like `traits_label` next to it, which is the same sentence in German and
was never capped. The two describing the same thing under different limits was
the asymmetry that made this possible.

No backfill and no rewrite: widening a varchar to text keeps every row as it
is. The downgrade cannot say the same -- it fails on any row past 120
characters, which after this revision is most of them, and that is honest: the
data no longer fits where it came from.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d7f41c9b3a26"
down_revision: Union[str, None] = "3ce81b27af40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "persona", "traits",
        existing_type=sa.String(length=120),
        type_=sa.Text(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "persona", "traits",
        existing_type=sa.Text(),
        type_=sa.String(length=120),
        existing_nullable=False,
    )
