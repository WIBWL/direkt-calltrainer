"""Join the library and feedback migration branches

Revision ID: c9e02b7a5f14
Revises: b3f2a91c04de, b4e1a72c9d05

Two branches grew from 9008fded73e9 in parallel -- the Persona/Scenario work
(ADR 0041/0043/0045) and the post-call Feedback work (ADR 0050/0051) -- and the
merge that brought them together left Alembic with two heads, so
`alembic upgrade head` refused to run.

A merge revision rather than re-pointing one branch onto the other: re-pointing
looks equivalent on an empty database, but Alembic plans upgrades from the
recorded version, not by walking the graph. A database already stamped at one
branch's head would compute a path that skips the other branch entirely and
report success, leaving columns silently missing. This node makes both branches
prerequisites, so every database reaches the same schema whichever head it is on.

Nothing to do here: both branches touch disjoint tables.
"""
from typing import Sequence, Union

revision: str = "c9e02b7a5f14"
down_revision: Union[str, Sequence[str], None] = ("b3f2a91c04de", "b4e1a72c9d05")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
