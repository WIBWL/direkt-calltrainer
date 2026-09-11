"""Aspect on metric_type

Revision ID: b6d24f7a91e5
Revises: c8b17d4e2f90

Which half of the Kennzahlen a metric belongs to: `how` the user sounded,
`what` the conversation consisted of. Display only, like `scenario.category`.

Nullable, so this runs on a seeded table without a NOT NULL backfill and a key
the inventory retires later needs no aspect; the CHECK passes for NULL. The
seeded rows are filled here so a hand-migrated database is not left
unclassified until the next provisioning run.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b6d24f7a91e5"
down_revision: Union[str, None] = "c8b17d4e2f90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The inventory at this revision. Spelled out rather than imported: the
# module moves on, a migration must not.
_HOW = ("pace", "reaction_time", "pauses", "loudness", "phase_appropriate_language",
        "congruence")
_WHAT = ("talk_share", "questions", "word_count", "concreteness")


def upgrade() -> None:
    op.add_column("metric_type", sa.Column("aspect", sa.String(length=10), nullable=True))
    # Autogenerate does not detect CHECKs; the bare name is right because
    # op.create_check_constraint applies the naming convention itself.
    op.create_check_constraint(
        "aspect_valid", "metric_type", "aspect IN ('how', 'what')",
    )
    metric_type = sa.table(
        "metric_type", sa.column("key", sa.String), sa.column("aspect", sa.String),
    )
    for aspect, keys in (("how", _HOW), ("what", _WHAT)):
        op.execute(
            metric_type.update().where(metric_type.c.key.in_(keys)).values(aspect=aspect)
        )


def downgrade() -> None:
    op.drop_constraint("aspect_valid", "metric_type", type_="check")
    op.drop_column("metric_type", "aspect")
