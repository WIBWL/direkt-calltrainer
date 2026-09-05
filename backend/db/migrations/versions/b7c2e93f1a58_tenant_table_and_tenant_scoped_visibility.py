"""Tenant table and tenant-scoped visibility

Revision ID: b7c2e93f1a58
Revises: a2f5c81b6e04

ADR 0060 (R-58 / F-59): a `tenant` table, a nullable `tenant_id` on `persona`
and `scenario`, and the `'tenant'` visibility value that shares an authored
Scenario with the author's company.

Two `visibility` CHECK swaps rather than one (ADR 0058's migration admitted only
private/public): the `'tenant'` value is meaningless without the tenant column,
so it could not have been written into the constraint earlier. A second CHECK
ties the two together -- `visibility = 'tenant'` requires `tenant_id`.

`tenant_id` is added nullable and left NULL on every existing row: those are all
shipped built-ins (ADR 0041), which belong to no tenant. Constraint names are
passed explicitly so they follow the convention on Base.metadata.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b7c2e93f1a58"
down_revision: Union[str, None] = "a2f5c81b6e04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("persona", "scenario")


def upgrade() -> None:
    op.create_table(
        "tenant",
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("extern_ref", sa.String(64), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.PrimaryKeyConstraint("tenant_id", name="pk_tenant"),
        sa.UniqueConstraint("extern_ref", name="uq_tenant_extern_ref"),
    )

    for table in _TABLES:
        op.add_column(table, sa.Column("tenant_id", sa.Integer(), nullable=True))
        # Composite, not single-column: the visibility filter is the hot path
        # (ADR 0060), and `tenant_id` first still covers the foreign key.
        op.create_index(
            f"ix_{table}_tenant_id_visibility", table, ["tenant_id", "visibility"]
        )
        op.create_foreign_key(
            f"fk_{table}_tenant_id_tenant", table, "tenant",
            ["tenant_id"], ["tenant_id"],
        )

        # Bare names: op.*_constraint applies the ck_ convention itself.
        op.drop_constraint("visibility_valid", table, type_="check")
        op.create_check_constraint(
            "visibility_valid", table,
            "visibility IN ('private', 'tenant', 'public')",
        )
        op.create_check_constraint(
            "tenant_visibility_needs_a_tenant", table,
            "visibility <> 'tenant' OR tenant_id IS NOT NULL",
        )


def downgrade() -> None:
    for table in _TABLES:
        op.drop_constraint("tenant_visibility_needs_a_tenant", table, type_="check")
        op.drop_constraint("visibility_valid", table, type_="check")
        op.create_check_constraint(
            "visibility_valid", table, "visibility IN ('private', 'public')"
        )
        op.drop_constraint(f"fk_{table}_tenant_id_tenant", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_tenant_id_visibility", table_name=table)
        op.drop_column(table, "tenant_id")

    op.drop_table("tenant")
