"""Display fields for the selection cards, and the case on the Scenario

Revision ID: d3b8f1a05c67
Revises: 5a7e1c9f4b02

The two columns ADR 0043 split off (`persona.role_label`, `scenario.
short_description`) and the three ADR 0045 puts on the Scenario (`case_facts`,
`call_goal`, `success_condition`).

Hand-written for the reason CLAUDE.md gives: autogenerate emits NOT NULL columns
with no backfill, which fails on tables that already hold the seeded library.
Each column is added nullable, backfilled, and only then tightened.

The two display fields are backfilled from their English prompt counterparts
rather than left blank -- a blank `role_label` is an empty selection card, and
the row is only corrected once the seed runs. The three case fields are
backfilled with the empty string instead, because empty is a legitimate value
there and not a migration artefact: a Scenario without a case behaves as it did
before ADR 0045 and improvises, which is what ADR 0024's user-authored ones will
do. Existing rows therefore stay valid after this runs.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d3b8f1a05c67"
down_revision: Union[str, None] = "5a7e1c9f4b02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, column, type, the SQL expression each existing row is backfilled with)
_COLUMNS = [
    ("persona", "role_label", sa.String(120), "role"),
    ("scenario", "short_description", sa.String(240), "title"),
    ("scenario", "case_facts", sa.Text(), "''"),
    ("scenario", "call_goal", sa.Text(), "''"),
    ("scenario", "success_condition", sa.Text(), "''"),
]


def upgrade() -> None:
    for table, column, type_, backfill in _COLUMNS:
        op.add_column(table, sa.Column(column, type_, nullable=True))
        op.execute(f"UPDATE {table} SET {column} = {backfill} WHERE {column} IS NULL")
        op.alter_column(table, column, existing_type=type_, nullable=False)


def downgrade() -> None:
    for table, column, _type, _backfill in reversed(_COLUMNS):
        op.drop_column(table, column)
