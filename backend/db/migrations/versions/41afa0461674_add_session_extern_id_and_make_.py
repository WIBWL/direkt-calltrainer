"""Add session extern_id and make timestamps timezone aware

Revision ID: 41afa0461674
Revises: e8ee215bf9bf
Create Date: 2026-08-27 16:17:35.120172

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '41afa0461674'
down_revision: Union[str, None] = 'e8ee215bf9bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Named explicitly: autogenerate emits create_unique_constraint(None, ...),
# which leaves the name to Postgres and makes drop_constraint(None) in
# downgrade() unrunnable.
UQ_SESSION_EXTERN_ID = "uq_session_extern_id"


def upgrade() -> None:
    """Gives Session the public id the client sees, and moves every timestamp
    to `timestamptz`.

    `extern_id` is added nullable, backfilled with a fresh UUID per existing
    row, and only then made NOT NULL — a plain NOT NULL add would fail on a
    populated table, and a single server default would make every row share one
    id and violate the unique constraint.
    """
    op.alter_column('analysis_job', 'aktualisiert_am',
               existing_type=postgresql.TIMESTAMP(),
               type_=sa.DateTime(timezone=True),
               existing_nullable=False)
    op.alter_column('feedback', 'erstellt_am',
               existing_type=postgresql.TIMESTAMP(),
               type_=sa.DateTime(timezone=True),
               existing_nullable=False)
    op.add_column('session', sa.Column('extern_id', sa.Uuid(), nullable=True))
    op.execute("UPDATE session SET extern_id = gen_random_uuid() WHERE extern_id IS NULL")
    op.alter_column('session', 'extern_id', nullable=False)
    op.alter_column('session', 'gestartet_am',
               existing_type=postgresql.TIMESTAMP(),
               type_=sa.DateTime(timezone=True),
               existing_nullable=False)
    op.alter_column('session', 'beendet_am',
               existing_type=postgresql.TIMESTAMP(),
               type_=sa.DateTime(timezone=True),
               existing_nullable=True)
    op.create_unique_constraint(UQ_SESSION_EXTERN_ID, 'session', ['extern_id'])


def downgrade() -> None:
    op.drop_constraint(UQ_SESSION_EXTERN_ID, 'session', type_='unique')
    op.alter_column('session', 'beendet_am',
               existing_type=sa.DateTime(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True)
    op.alter_column('session', 'gestartet_am',
               existing_type=sa.DateTime(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=False)
    op.drop_column('session', 'extern_id')
    op.alter_column('feedback', 'erstellt_am',
               existing_type=sa.DateTime(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=False)
    op.alter_column('analysis_job', 'aktualisiert_am',
               existing_type=sa.DateTime(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=False)
    # ### end Alembic commands ###
