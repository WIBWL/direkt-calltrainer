"""Drop the scenario_type column

Revision ID: e4a9c07b2f31
Revises: b7c2e93f1a58

`scenario.scenario_type` was a loose free-text label that nothing read -- not
the prompt (`backend/session/orchestrator.py` never touched it), not the
selection card, not a filter. The library filters ran on `origin` / `shared`
(ADR 0060) alone. So the column goes.

Its ADR was withdrawn once the category came back as a closed vocabulary that a
filter does read; ADR 0064 records both halves and the number 0062 stays
unused. This revision itself stands: `f5b2d47a91c3` adds `category` as a new
column rather than reviving this one.

The downgrade re-adds it NOT NULL with a `''` server default (there is no value
to backfill), then drops the default to match the model, which declared none.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e4a9c07b2f31"
down_revision: Union[str, None] = "b7c2e93f1a58"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("scenario", "scenario_type")


def downgrade() -> None:
    op.add_column(
        "scenario",
        sa.Column(
            "scenario_type",
            sa.String(length=60),
            nullable=False,
            server_default="",
        ),
    )
    op.alter_column("scenario", "scenario_type", server_default=None)
