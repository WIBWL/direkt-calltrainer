"""Add persona detail fields, persona_einwand and stable schluessel keys

Revision ID: 9008fded73e9
Revises: 30351586b0a1
Create Date: 2026-08-17 22:36:37.042447

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9008fded73e9'
down_revision: Union[str, None] = '30351586b0a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('persona_einwand',
    sa.Column('einwand_id', sa.Integer(), nullable=False),
    sa.Column('persona_id', sa.Integer(), nullable=False),
    sa.Column('reihenfolge', sa.Integer(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['persona_id'], ['persona.persona_id'], ),
    sa.PrimaryKeyConstraint('einwand_id')
    )

    # The new columns are NOT NULL, but the tables already hold reference
    # rows. Hence three steps: add as nullable -> backfill -> set NOT NULL.
    op.add_column('persona', sa.Column('schluessel', sa.String(length=60), nullable=True))
    op.add_column('persona', sa.Column('verhalten', sa.Text(), nullable=True))
    op.add_column('persona', sa.Column('trainingsziel', sa.Text(), nullable=True))
    op.add_column('szenario', sa.Column('schluessel', sa.String(length=60), nullable=True))

    # schluessel has to be set correctly: the seed script recognises the rows
    # by it. A wrong value would make the seed script insert a duplicate.
    op.execute(
        "UPDATE persona SET schluessel = 'tech-averse-management' "
        "WHERE name = 'Technikaverses Management'"
    )
    op.execute(
        "UPDATE szenario SET schluessel = 'cold-call-followup' "
        "WHERE titel = 'Follow-up-/Closing-Call nach Kaltakquise'"
    )
    # Fallback for unknown rows, so that NOT NULL is guaranteed to hold.
    op.execute(
        "UPDATE persona SET schluessel = 'persona-' || persona_id "
        "WHERE schluessel IS NULL"
    )
    op.execute(
        "UPDATE szenario SET schluessel = 'szenario-' || szenario_id "
        "WHERE schluessel IS NULL"
    )
    # verhalten/trainingsziel stay empty — the content comes from
    # scripts/seed_reference_data.py, which runs after the migration.
    op.execute("UPDATE persona SET verhalten = '' WHERE verhalten IS NULL")
    op.execute("UPDATE persona SET trainingsziel = '' WHERE trainingsziel IS NULL")

    op.alter_column('persona', 'schluessel', nullable=False)
    op.alter_column('persona', 'verhalten', nullable=False)
    op.alter_column('persona', 'trainingsziel', nullable=False)
    op.alter_column('szenario', 'schluessel', nullable=False)

    op.create_unique_constraint('uq_persona_schluessel', 'persona', ['schluessel'])
    op.create_unique_constraint('uq_szenario_schluessel', 'szenario', ['schluessel'])


def downgrade() -> None:
    op.drop_constraint('uq_szenario_schluessel', 'szenario', type_='unique')
    op.drop_column('szenario', 'schluessel')
    op.drop_constraint('uq_persona_schluessel', 'persona', type_='unique')
    op.drop_column('persona', 'trainingsziel')
    op.drop_column('persona', 'verhalten')
    op.drop_column('persona', 'schluessel')
    op.drop_table('persona_einwand')
