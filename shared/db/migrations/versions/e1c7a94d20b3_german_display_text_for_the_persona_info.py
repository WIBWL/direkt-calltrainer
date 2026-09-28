"""German display text for the Persona info panel

Two display-only columns beside their English prompt counterparts, the same
split `persona.role_label` already makes against `persona.role` (ADR 0043):
the prompt fields stay English because the model reads them, and the info panel
on the selection card needs the same content in the UI language.

Both are nullable. They carry no meaning for a call — a Persona without them is
fully playable and the panel simply omits the line — and a NOT NULL column
added to a seeded table would need a backfill that invents text.

Revision ID: e1c7a94d20b3
Revises: c8d1f3a67b40
Create Date: 2026-09-09

"""
from alembic import op
import sqlalchemy as sa

revision = "e1c7a94d20b3"
down_revision = "c8d1f3a67b40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("persona", sa.Column("traits_label", sa.Text(), nullable=True))
    op.add_column("persona_objection", sa.Column("text_label", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("persona_objection", "text_label")
    op.drop_column("persona", "traits_label")
