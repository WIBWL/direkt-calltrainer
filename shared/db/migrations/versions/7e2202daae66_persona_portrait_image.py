"""Portrait image for a Persona

One display-only column holding the path a Persona's portrait is served from,
e.g. /personas/andreas-kastner-ceo.webp. The images themselves are ordinary
frontend assets in `frontend/public/personas/`; only the pairing belongs in the
table, so that adding a Persona stays a seed change plus a file (ADR 0041).

Nullable, like every other display-only column on `persona` (ADR 0043's split
put them there): a Persona without a picture is fully playable and the UI shows
its initials instead, and a NOT NULL column on a seeded table would need a
backfill that has nothing to fill in.

Revision ID: 7e2202daae66
Revises: b2e8d4f19c07
Create Date: 2026-09-10

"""
from alembic import op
import sqlalchemy as sa

revision = "7e2202daae66"
down_revision = "b2e8d4f19c07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("persona", sa.Column("avatar_url", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column("persona", "avatar_url")
