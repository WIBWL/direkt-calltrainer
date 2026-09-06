"""Retention preference

Revision ID: 40bd4a8839f2
Revises: a4d3558cbc0b

One row per subject who switched the six-month sweep off (ADR 0061). Absence of
a row means the sweep applies, which is what makes the retention period the
default rather than something each account opts into.

`subject_id` is unique rather than merely indexed: a subject has one answer to
this question, and two rows would make the sweep's behaviour depend on which
one it happened to read. No foreign key, for the same reason `session.subject_id`
has none (ADR 0031).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '40bd4a8839f2'
down_revision: Union[str, None] = 'a4d3558cbc0b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('retention_preference',
    sa.Column('preference_id', sa.Integer(), nullable=False),
    sa.Column('subject_id', sa.String(length=64), nullable=False),
    sa.Column('auto_delete', sa.Boolean(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('preference_id', name=op.f('pk_retention_preference')),
    sa.UniqueConstraint('subject_id', name=op.f('uq_retention_preference_subject_id'))
    )


def downgrade() -> None:
    op.drop_table('retention_preference')
