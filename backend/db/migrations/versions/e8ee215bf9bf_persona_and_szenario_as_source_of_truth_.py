"""Persona and szenario as source of truth for language voice and availability

Revision ID: e8ee215bf9bf
Revises: 5bc6435e9543
Create Date: 2026-08-27 15:58:44.793770

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8ee215bf9bf'
down_revision: Union[str, None] = '5bc6435e9543'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Named explicitly: autogenerate emits create_foreign_key(None, ...), which
# leaves Postgres to invent the name and makes the matching drop_constraint(None)
# in downgrade() unrunnable.
FK_PERSONA_SPRACHE = "persona_sprache_code_fkey"


def upgrade() -> None:
    """Moves Language and voice onto the Persona and gives Szenario an `aktiv`
    flag, so `persona`/`szenario` can be the source of truth that
    `backend/personas.py` and `backend/scenarios.py` merely seed.

    The NOT NULL columns are added with a server default that is dropped right
    after, because `persona` already has rows and autogenerate's plain NOT NULL
    would fail on them. Existing Personas are backfilled to German with the
    default German voice — the only Language the product supports today.
    """
    op.add_column('persona', sa.Column('sprache_code', sa.String(length=8), nullable=False, server_default='de'))
    op.add_column('persona', sa.Column('tts_voice', sa.String(length=60), nullable=False, server_default='de_male'))
    op.add_column('persona', sa.Column('kugelaudio_voice_id', sa.Integer(), nullable=True))
    op.alter_column('persona', 'sprache_code', server_default=None)
    op.alter_column('persona', 'tts_voice', server_default=None)
    op.create_foreign_key(FK_PERSONA_SPRACHE, 'persona', 'sprache', ['sprache_code'], ['sprache_code'])

    # Existing Szenarien predate the flag and are all still offered.
    op.add_column('szenario', sa.Column('aktiv', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.alter_column('szenario', 'aktiv', server_default=None)


def downgrade() -> None:
    op.drop_column('szenario', 'aktiv')
    op.drop_constraint(FK_PERSONA_SPRACHE, 'persona', type_='foreignkey')
    op.drop_column('persona', 'kugelaudio_voice_id')
    op.drop_column('persona', 'tts_voice')
    op.drop_column('persona', 'sprache_code')
