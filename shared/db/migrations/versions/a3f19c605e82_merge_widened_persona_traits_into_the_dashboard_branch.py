"""Merge dev's widened persona traits into the dashboard branch

Two heads, one per branch of the git merge this accompanies: `d7f41c9b3a26`
widened `persona.traits`, `9d2e6b4c1a07` is the dashboard branch's own merge of
the segment measurements. They touch different tables and neither depends on
the other, so this revision only rejoins the chain and has nothing of its own
to do.

Written by hand rather than by `alembic merge`, for the reason `c4f7a2e910bd`
gives -- a defect in `18f5098dfb1b` that broke every Alembic command except
`upgrade`. It has since been fixed; the command works again.

Empty on purpose. A merge revision carries no DDL -- both parents are already
applied by the time it runs, whichever order they ran in -- so `upgrade` and
`downgrade` are `pass`, and a database that followed either branch reaches the
same schema.

Revision ID: a3f19c605e82
Revises: 9d2e6b4c1a07, d7f41c9b3a26
Create Date: 2026-09-12

"""

revision = "a3f19c605e82"
down_revision = ("9d2e6b4c1a07", "d7f41c9b3a26")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
