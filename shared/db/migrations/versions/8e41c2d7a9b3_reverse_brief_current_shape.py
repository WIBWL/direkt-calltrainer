"""Stored reverse briefings brought to the current shape

Revision ID: 8e41c2d7a9b3
Revises: b3f07c5a91d4

A reverse's `reverse_brief` (ADR 0070) is written once and never regenerated,
so briefings from before two changes to its shape still carry the old keys:
`settled`, merged into `goal`, and `watch_points`, renamed to `goals`. The
frontend read both as fallbacks. This rewrites them, so the client needs to know
one shape only: `settled` is appended to `goal` exactly as the client joined
them, `watch_points` becomes `goals` where no `goals` list exists, and a
briefing with neither gets an empty list.

The downgrade is a no-op: the current shape is what the older client read
first, so nothing it needs is lost.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "8e41c2d7a9b3"
down_revision: Union[str, None] = "b3f07c5a91d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE scenario
        SET reverse_brief = (reverse_brief - 'settled') || jsonb_build_object(
            'goal',
            trim(coalesce(reverse_brief->>'goal', '') || ' '
                 || coalesce(reverse_brief->>'settled', ''))
        )
        WHERE reverse_brief ? 'settled'
        """
    )
    op.execute(
        """
        UPDATE scenario
        SET reverse_brief = (reverse_brief - 'watch_points') || CASE
            WHEN jsonb_typeof(reverse_brief->'goals') = 'array' THEN '{}'::jsonb
            WHEN jsonb_typeof(reverse_brief->'watch_points') = 'array'
                THEN jsonb_build_object('goals', reverse_brief->'watch_points')
            ELSE '{}'::jsonb
        END
        WHERE reverse_brief ? 'watch_points'
        """
    )
    op.execute(
        """
        UPDATE scenario
        SET reverse_brief = reverse_brief || '{"goals": []}'::jsonb
        WHERE reverse_brief IS NOT NULL
          AND jsonb_typeof(reverse_brief->'goals') IS DISTINCT FROM 'array'
        """
    )


def downgrade() -> None:
    pass
