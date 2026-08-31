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

    # Die neuen Spalten sind NOT NULL, die Tabellen enthalten aber bereits
    # Referenzzeilen. Daher dreistufig: nullable anlegen -> befuellen ->
    # NOT NULL setzen.
    op.add_column('persona', sa.Column('schluessel', sa.String(length=60), nullable=True))
    op.add_column('persona', sa.Column('verhalten', sa.Text(), nullable=True))
    op.add_column('persona', sa.Column('trainingsziel', sa.Text(), nullable=True))
    op.add_column('szenario', sa.Column('schluessel', sa.String(length=60), nullable=True))

    # schluessel muss korrekt gesetzt werden: das Seed-Skript erkennt die
    # Zeilen daran wieder. Ein falscher Wert wuerde dort ein Duplikat anlegen.
    op.execute(
        "UPDATE persona SET schluessel = 'tech-averse-management' "
        "WHERE name = 'Technikaverses Management'"
    )
    op.execute(
        "UPDATE szenario SET schluessel = 'cold-call-followup' "
        "WHERE titel = 'Follow-up-/Closing-Call nach Kaltakquise'"
    )
    # Fallback fuer unbekannte Zeilen, damit NOT NULL sicher greift.
    op.execute(
        "UPDATE persona SET schluessel = 'persona-' || persona_id "
        "WHERE schluessel IS NULL"
    )
    op.execute(
        "UPDATE szenario SET schluessel = 'szenario-' || szenario_id "
        "WHERE schluessel IS NULL"
    )
    # verhalten/trainingsziel bleiben leer — die Inhalte liefert
    # scripts/seed_reference_data.py, das nach der Migration laeuft.
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
