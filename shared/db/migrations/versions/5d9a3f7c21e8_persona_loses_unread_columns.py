"""Persona loses the columns nothing reads

Revision ID: 5d9a3f7c21e8
Revises: 8e41c2d7a9b3

A Persona is curated, never authored (ADR 0058), and is listed without any
visibility filter, so the authorship columns it carried "for symmetry" with
`scenario` -- `created_by`, `tenant_id`, `visibility`, their index and their two
CHECKs -- were written by the seed and read by nothing. `difficulty` was the
same: seeded, never served, never read by the prompt. All five go.

`extern_id`, `created_at` and `updated_at` stay; the client addresses a Persona
by the first.

The downgrade restores the columns with the values every row held: no author,
no company, `public`, and `medium` for the difficulty, which is the truthful
answer only in aggregate -- what each Persona was seeded with is not
recoverable from the rows.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "5d9a3f7c21e8"
down_revision: Union[str, None] = "8e41c2d7a9b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Bare names: op.drop_constraint applies the ck_ convention itself.
    op.drop_constraint("tenant_visibility_needs_a_tenant", "persona", type_="check")
    op.drop_constraint("visibility_valid", "persona", type_="check")
    op.drop_constraint("fk_persona_tenant_id_tenant", "persona", type_="foreignkey")
    op.drop_index("ix_persona_tenant_id_visibility", table_name="persona")
    op.drop_index("ix_persona_created_by", table_name="persona")
    for column in ("tenant_id", "visibility", "created_by", "difficulty"):
        op.drop_column("persona", column)


def downgrade() -> None:
    op.add_column("persona", sa.Column("difficulty", sa.String(40), nullable=True))
    op.add_column("persona", sa.Column("created_by", sa.String(64), nullable=True))
    op.add_column("persona", sa.Column("visibility", sa.String(12), nullable=True))
    op.add_column("persona", sa.Column("tenant_id", sa.Integer(), nullable=True))
    op.execute("UPDATE persona SET difficulty = 'medium', visibility = 'public'")
    op.alter_column("persona", "difficulty", existing_type=sa.String(40), nullable=False)
    op.alter_column("persona", "visibility", existing_type=sa.String(12), nullable=False)
    op.create_index("ix_persona_created_by", "persona", ["created_by"])
    op.create_index("ix_persona_tenant_id_visibility", "persona", ["tenant_id", "visibility"])
    op.create_foreign_key(
        "fk_persona_tenant_id_tenant", "persona", "tenant", ["tenant_id"], ["tenant_id"]
    )
    op.create_check_constraint(
        "visibility_valid", "persona", "visibility IN ('private', 'tenant', 'public')"
    )
    op.create_check_constraint(
        "tenant_visibility_needs_a_tenant", "persona",
        "visibility <> 'tenant' OR tenant_id IS NOT NULL",
    )
