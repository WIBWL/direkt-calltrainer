"""German display text for the Scenario read view

Display twins of `scenario.description` and `scenario.case_facts`, the same
split ADR 0076 already relies on for `persona.traits_label`: the prompt fields
stay English so a Persona's language alone decides the call's (ADR 0043), and
the read view behind a card shows the same content in the UI language.

Nullable, and only the seed writes them. An authored Scenario is already in its
author's language, so both stay NULL there and the API serves the field itself.

Revision ID: b2e8d4f19c07
Revises: e1c7a94d20b3
Create Date: 2026-09-09

"""
from alembic import op
import sqlalchemy as sa

revision = "b2e8d4f19c07"
down_revision = "e1c7a94d20b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scenario", sa.Column("description_label", sa.Text(), nullable=True))
    op.add_column("scenario", sa.Column("case_facts_label", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("scenario", "case_facts_label")
    op.drop_column("scenario", "description_label")
