"""Reverse marker, origin session and briefing on scenario

Revision ID: c8b17d4e2f90
Revises: dc5b4557e6b1

ADR 0070: a reverse replays one finished Session with the roles swapped, and is
a Scenario row carrying a marker rather than a Session mode. Three columns.

Re-pointed from `f5b2d47a91c3` onto `dc5b4557e6b1` when this branch caught up
with dev: both had been written against the same parent, which leaves the chain
with two heads and every migration failing. The columns are additive and
independent of the follow-up provenance that revision adds, so the order is
free -- the same situation, and the same fix, as `f5b2d47a91c3` records.

`reverse` is NOT NULL and the table is not empty, so it is added with a server
default, backfilled by it, and then stripped of that default: every existing
Scenario is an ordinary one. The default is dropped again because the model
declares a Python-side default only (CLAUDE.md) -- leaving it would let a row
inserted from psql disagree with a row inserted by the app about which side of
the schema owns the value.

`origin_session_id` is the one foreign key in the schema pointing from a
reference table back into a Session. It is `ON DELETE SET NULL`, so deleting a
training leaves the reverse made from it standing (ADR 0070's deletion rule),
and UNIQUE, so a Session has at most one reverse and the create route is
idempotent. The unique constraint's index is what satisfies ADR 0052 here; no
second index is created.

The CHECK ties the briefing to the marker. Alembic does not autodetect CHECK
constraints, so it is written by hand, with the bare name -- op.create_check_
constraint applies the naming convention itself (ADR 0053).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c8b17d4e2f90"
down_revision: Union[str, None] = "dc5b4557e6b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "scenario",
        sa.Column("reverse", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # The column exists to carry the app's Python-side default from here on;
    # the server default was only there to fill the rows already in the table.
    op.alter_column("scenario", "reverse", server_default=None)

    op.add_column("scenario", sa.Column("origin_session_id", sa.Integer(), nullable=True))
    op.add_column(
        "scenario", sa.Column("reverse_brief", postgresql.JSONB(), nullable=True)
    )
    op.create_unique_constraint(
        op.f("uq_scenario_origin_session_id"), "scenario", ["origin_session_id"]
    )
    op.create_foreign_key(
        op.f("fk_scenario_origin_session_id_session"),
        "scenario",
        "session",
        ["origin_session_id"],
        ["session_id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "brief_only_on_a_reverse", "scenario", "reverse OR reverse_brief IS NULL"
    )


def downgrade() -> None:
    op.drop_constraint("brief_only_on_a_reverse", "scenario", type_="check")
    op.drop_constraint(
        op.f("fk_scenario_origin_session_id_session"), "scenario", type_="foreignkey"
    )
    op.drop_constraint(
        op.f("uq_scenario_origin_session_id"), "scenario", type_="unique"
    )
    op.drop_column("scenario", "reverse_brief")
    op.drop_column("scenario", "origin_session_id")
    op.drop_column("scenario", "reverse")
