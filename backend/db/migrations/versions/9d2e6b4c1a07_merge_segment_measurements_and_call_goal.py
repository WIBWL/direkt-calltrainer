"""Merge the dashboard branch's segment measurements into dev's call-goal merge

Two heads, one per branch of the git merge this accompanies:
`f3a5c81be47d` added `measurement.segment` and `turn.acoustics_json`
(ADR 0081), `3ce81b27af40` folded `scenario.success_condition` into
`scenario.call_goal`. They touch different tables and neither depends on the
other, so this revision only rejoins the chain and has nothing of its own to
do.

Written by hand rather than by `alembic merge`, for the reason
`c4f7a2e910bd` gives: `18f5098dfb1b` calls `op.f()` at module level, and every
Alembic command that loads all revisions at once dies on it before reaching
the merge. `upgrade` is unaffected.

Empty on purpose. A merge revision carries no DDL -- both parents are already
applied by the time it runs, whichever order they ran in -- so `upgrade` and
`downgrade` are `pass`, and a database that followed either branch reaches the
same schema.

Revision ID: 9d2e6b4c1a07
Revises: f3a5c81be47d, 3ce81b27af40
Create Date: 2026-09-11

"""

revision = "9d2e6b4c1a07"
down_revision = ("f3a5c81be47d", "3ce81b27af40")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
