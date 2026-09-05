"""Authored-content columns on persona and scenario

Revision ID: a2f5c81b6e04
Revises: c1f4a83b7d29

ADR 0058: the columns that let a User author their own Scenario -- `created_by`
(authorship), `visibility` (who may see it), `extern_id` (the id the client
uses, ADR 0050), and `created_at` / `updated_at`. The same columns land on
`persona` for schema symmetry, though Personas stay curated. The owning-company
axis (`tenant_id`) is ADR 0060 and follows in the next migration.

Hand-written for the reason CLAUDE.md gives -- autogenerate adds NOT NULL columns
with no backfill and does not emit CHECK constraints. Every existing row is a
shipped built-in (ADR 0041), so:

  * `visibility` backfills to 'public' -- a built-in is visible to everyone;
  * `extern_id` backfills with `gen_random_uuid()` (Postgres 13+ core), then the
    server default is dropped so new rows get their id from the ORM's
    `default=uuid.uuid4`, exactly as `session.extern_id` does;
  * `created_at` / `updated_at` take `now()` for the rows that predate them;
  * `key` becomes nullable -- an authored row has no slug -- but keeps its
    unique constraint (Postgres allows many NULLs in a UNIQUE column).

This `visibility` CHECK admits only ('private','public'); ADR 0060's migration
widens it to include 'tenant'. Two constraint swaps rather than one is
deliberate: the 'tenant' value is meaningless until the tenant column exists.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a2f5c81b6e04"
down_revision: Union[str, None] = "c1f4a83b7d29"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("persona", "scenario")


def upgrade() -> None:
    for table in _TABLES:
        # An authored row is addressed by extern_id; only built-ins carry a slug.
        op.alter_column(table, "key", existing_type=sa.String(60), nullable=True)

        op.add_column(table, sa.Column("created_by", sa.String(64), nullable=True))
        op.create_index(f"ix_{table}_created_by", table, ["created_by"])

        op.add_column(table, sa.Column("visibility", sa.String(12), nullable=True))
        op.execute(f"UPDATE {table} SET visibility = 'public' WHERE visibility IS NULL")
        op.alter_column(table, "visibility", existing_type=sa.String(12), nullable=False)
        # Bare name: op.create_check_constraint applies the ck_ convention itself.
        op.create_check_constraint(
            "visibility_valid", table, "visibility IN ('private', 'public')"
        )

        op.add_column(
            table,
            sa.Column(
                "extern_id",
                sa.Uuid(),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
        )
        op.alter_column(table, "extern_id", server_default=None)
        op.create_unique_constraint(f"uq_{table}_extern_id", table, ["extern_id"])

        for column in ("created_at", "updated_at"):
            op.add_column(
                table,
                sa.Column(
                    column,
                    sa.DateTime(timezone=True),
                    server_default=sa.text("now()"),
                    nullable=False,
                ),
            )


def downgrade() -> None:
    for table in _TABLES:
        op.drop_column(table, "updated_at")
        op.drop_column(table, "created_at")
        op.drop_constraint(f"uq_{table}_extern_id", table, type_="unique")
        op.drop_column(table, "extern_id")
        op.drop_constraint("visibility_valid", table, type_="check")
        op.drop_column(table, "visibility")
        op.drop_index(f"ix_{table}_created_by", table_name=table)
        op.drop_column(table, "created_by")
        op.alter_column(table, "key", existing_type=sa.String(60), nullable=False)
