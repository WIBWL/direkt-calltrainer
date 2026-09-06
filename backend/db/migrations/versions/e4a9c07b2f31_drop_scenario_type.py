"""Drop the scenario_type column

Revision ID: e4a9c07b2f31
Revises: b7c2e93f1a58

ADR 0062: `scenario.scenario_type` was a loose category label that nothing read
-- not the prompt (`backend/session/orchestrator.py` never touched it), not the
selection card, not a filter. The four library filters run on `origin` /
`shared` (ADR 0060), and F-03's spread of call contexts is carried by the
Scenarios themselves, not by a label on the row. So the column goes.

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
