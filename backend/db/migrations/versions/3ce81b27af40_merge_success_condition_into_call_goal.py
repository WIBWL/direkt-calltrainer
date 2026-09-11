"""Merge success_condition into call_goal

Revision ID: 3ce81b27af40
Revises: c4f7a2e910bd

`scenario.call_goal` said what the caller wants and `scenario.success_condition`
the bar they judged it by. They were two fields with one audience -- both went
to the model playing the caller, both were weighed the same way (silently,
against what has actually been said, never recited back), and a goal written
without a bar is half a case. The editor asked for them separately, which is
where the split came from and the only place it ever showed.

The texts are concatenated before the column goes, so nothing authored is lost.
They are joined by a newline rather than rewritten into one sentence: this is
the Users' own prose and the migration is in no position to paraphrase it. The
seeded rows are not patched here at all -- `backend/db/seed_data.py` carries
them already merged, and provisioning upserts them on the next start.

The downgrade re-adds the column NOT NULL with a `''` server default and then
drops the default, matching the model, which declared none. It cannot undo the
merge: once the two texts are one, no rule tells them apart again. That is
stated rather than attempted.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "3ce81b27af40"
down_revision: Union[str, None] = "c4f7a2e910bd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Only where there is something on both sides: an empty half must not
    # leave a stray separator at the front or the end of the field.
    op.execute(
        sa.text(
            """
            UPDATE scenario
               SET call_goal = CASE
                     WHEN COALESCE(call_goal, '') = '' THEN COALESCE(success_condition, '')
                     WHEN COALESCE(success_condition, '') = '' THEN call_goal
                     ELSE call_goal || CHR(10) || success_condition
                   END
            """
        )
    )
    op.drop_column("scenario", "success_condition")


def downgrade() -> None:
    op.add_column(
        "scenario",
        sa.Column("success_condition", sa.Text(), nullable=False, server_default=""),
    )
    op.alter_column("scenario", "success_condition", server_default=None)
