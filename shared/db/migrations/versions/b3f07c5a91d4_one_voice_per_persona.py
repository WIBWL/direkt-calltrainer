"""One voice per Persona: the fallback backend's voice column goes

Revision ID: b3f07c5a91d4
Revises: c1a6b8407f52

ADR 0103. Speech output is KugelAudio and nothing else, so a Persona has one
voice. `persona.tts_voice` named the voice on the gateway's own TTS model,
which was KugelAudio's fallback (ADR 0040) and is no longer reached from
anywhere; it is dropped rather than left behind, because a column every seeded
Persona has to carry and nothing reads is the kind of thing that gets filled in
again by someone reading the table rather than the code.

`persona.kugelaudio_voice_id` stays nullable on purpose. It is now the only
voice there is, so a Persona without one cannot be played -- but that is what
`active` says, and the seed already pairs the two
(`tests/test_persona_scenario_library.py`). Making it NOT NULL here would mean
deciding what to do with a row that has no voice and a Session pointing at it,
and inventing a voice id for it is the one answer that would be wrong.

The downgrade re-adds the column and fills it with `de_male`, which is the
truthful answer and not the original one: the fallback model only ever carried
German voices, and what each Persona used to name is not recoverable from the
rows.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b3f07c5a91d4"
down_revision: Union[str, None] = "c1a6b8407f52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("persona", "tts_voice")


def downgrade() -> None:
    op.add_column("persona", sa.Column("tts_voice", sa.String(60), nullable=True))
    op.execute("UPDATE persona SET tts_voice = 'de_male' WHERE tts_voice IS NULL")
    op.alter_column("persona", "tts_voice", existing_type=sa.String(60), nullable=False)
