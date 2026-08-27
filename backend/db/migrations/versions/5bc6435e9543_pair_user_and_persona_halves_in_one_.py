"""Pair user and persona halves in one turn row

Revision ID: 5bc6435e9543
Revises: 9008fded73e9
Create Date: 2026-08-27 15:02:55.621968

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5bc6435e9543'
down_revision: Union[str, None] = '9008fded73e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """A Turn becomes one exchange (user half + persona half) instead of one
    utterance of one speaker, so `sprecher` disappears and both transcripts and
    durations move into their own columns. `start_offset_ms` is dropped without
    replacement: a paired Turn has two start times, `seq_index` already carries
    the ordering, and no Session audio is stored to align against (ADR 0034).

    The new text columns are added WITH a server default and stripped of it
    right after, so this also applies to a table that already has rows —
    autogenerate's plain NOT NULL would fail there.
    """
    op.add_column('turn', sa.Column('nutzer_transkript', sa.Text(), nullable=False, server_default=''))
    op.add_column('turn', sa.Column('persona_transkript', sa.Text(), nullable=False, server_default=''))
    op.alter_column('turn', 'nutzer_transkript', server_default=None)
    op.alter_column('turn', 'persona_transkript', server_default=None)

    # Nullable: a Turn can legitimately lack one half — the opening Turn has no
    # user utterance, a Turn cut short by a pipeline failure (ADR 0016) no
    # persona reply.
    op.add_column('turn', sa.Column('nutzer_dauer_ms', sa.Integer(), nullable=True))
    op.add_column('turn', sa.Column('persona_dauer_ms', sa.Integer(), nullable=True))

    op.drop_column('turn', 'dauer_ms')
    op.drop_column('turn', 'start_offset_ms')
    op.drop_column('turn', 'sprecher')
    op.drop_column('turn', 'transkript')


def downgrade() -> None:
    """Restores the previous column shape, not the previous data.

    Splitting a paired row back into one row per speaker would have to invent
    turn_ids, and `messung`, `befund` and `feedbackpunkt` all reference
    `turn.turn_id` — so their rows could not follow the split. This downgrade
    is therefore only meaningful on an empty `turn` table; the server defaults
    exist so it does not error out on a populated one, which would leave the
    speaker attribution wrong rather than absent.
    """
    op.add_column('turn', sa.Column('transkript', sa.TEXT(), autoincrement=False, nullable=False, server_default=''))
    op.add_column('turn', sa.Column('sprecher', sa.VARCHAR(length=10), autoincrement=False, nullable=False, server_default='nutzer'))
    op.add_column('turn', sa.Column('start_offset_ms', sa.INTEGER(), autoincrement=False, nullable=False, server_default='0'))
    op.add_column('turn', sa.Column('dauer_ms', sa.INTEGER(), autoincrement=False, nullable=False, server_default='0'))
    op.alter_column('turn', 'transkript', server_default=None)
    op.alter_column('turn', 'sprecher', server_default=None)
    op.alter_column('turn', 'start_offset_ms', server_default=None)
    op.alter_column('turn', 'dauer_ms', server_default=None)

    op.drop_column('turn', 'persona_dauer_ms')
    op.drop_column('turn', 'nutzer_dauer_ms')
    op.drop_column('turn', 'persona_transkript')
    op.drop_column('turn', 'nutzer_transkript')
