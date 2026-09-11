"""Merge the persona-portrait branch into dev's

Two heads, one per branch of the git merge this accompanies: `7e2202daae66`
added `persona.avatar_url`, `b6d24f7a91e5` added `metric_type.aspect`. They
touch different tables and neither depends on the other, so this revision only
rejoins the chain and has nothing of its own to do.

Written by hand rather than by `alembic merge`, which cannot run in this
repository: `18f5098dfb1b` calls `op.f()` at module level, and every Alembic
command that loads all revisions at once dies on it before reaching the merge.
`upgrade` is unaffected, which is why the defect has stayed hidden.

Empty on purpose. A merge revision carries no DDL -- both parents are already
applied by the time it runs, whichever order they ran in -- so `upgrade` and
`downgrade` are `pass`, and a database that followed either branch reaches the
same schema.

Revision ID: c4f7a2e910bd
Revises: 7e2202daae66, b6d24f7a91e5
Create Date: 2026-09-11

"""

revision = "c4f7a2e910bd"
down_revision = ("7e2202daae66", "b6d24f7a91e5")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
