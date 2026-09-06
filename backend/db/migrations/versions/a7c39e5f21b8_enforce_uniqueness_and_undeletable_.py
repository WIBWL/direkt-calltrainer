"""Enforce the invariants the schema only described

Revision ID: a7c39e5f21b8
Revises: c1f4a83b7d29

Three rules the code assumed and the database did not hold anyone to.

`measurement` gets one row per Session and metric type. "Exactly one set of
statistics per Session" (ADR 0051) lived in a docstring and in the fact that
`session/persistence.py` happens to be the only writer; a retried job or a
later "recalculate" would have stored a second speaking rate for the same call,
and `api/sessions.py` would have rendered both.

`turn` gets one row per Session and position. The transcript is ordered by
`seq_index` alone, so two rows sharing one would come back in an order Postgres
is free to choose -- differently on each read.

`finding.metric_type_id` and `feedback_point.metric_type_id` lose their
`ON DELETE SET NULL`. Both point at a reference table, where the schema's rule
is that a referenced row must not be deletable at all (ADR 0026). The clause
was also unreachable: `measurement.metric_type_id` has no such clause, so a
`metric_type` in use could never be deleted in the first place, and the two
SET NULLs described a behaviour that could not occur. Written out rather than
left, because the next person to touch `measurement` would have switched it on
without deciding to.

`finding.offset_ms` gains the non-negative CHECK its counterpart on `turn`
already had.

Written by hand: autogenerate detects neither CHECK constraints nor a changed
`ondelete` (ADR 0027, CLAUDE.md).

Note on existing data: the two unique constraints fail if a database already
holds duplicates. None can exist through the application -- both tables have a
single writer, inside one transaction per Session -- but a database filled by
`scripts/stress_db.py` or by hand should be checked before this is applied.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a7c39e5f21b8"
down_revision: Union[str, None] = "c1f4a83b7d29"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Names as the convention on Base.metadata renders them (ADR 0053). The unique
# convention is uq_%(table_name)s_%(column_0_name)s and carries no
# %(constraint_name)s, so the full name is passed here; the check convention
# does carry it, so those take the bare name and op prefixes it.
UQ_MEASUREMENT = "uq_measurement_session_id"
UQ_TURN = "uq_turn_session_id"
CK_FINDING_OFFSET = "offset_non_negative"
FK_FINDING_METRIC = "fk_finding_metric_type_id_metric_type"
FK_POINT_METRIC = "fk_feedback_point_metric_type_id_metric_type"


def upgrade() -> None:
    op.create_unique_constraint(
        UQ_MEASUREMENT, "measurement", ["session_id", "metric_type_id"]
    )
    op.create_unique_constraint(UQ_TURN, "turn", ["session_id", "seq_index"])

    op.create_check_constraint(
        CK_FINDING_OFFSET, "finding", "offset_ms IS NULL OR offset_ms >= 0"
    )

    # A foreign key's ondelete cannot be altered in place; it is dropped and
    # recreated without the clause.
    op.drop_constraint(FK_FINDING_METRIC, "finding", type_="foreignkey")
    op.create_foreign_key(
        FK_FINDING_METRIC, "finding", "metric_type",
        ["metric_type_id"], ["metric_type_id"],
    )
    op.drop_constraint(FK_POINT_METRIC, "feedback_point", type_="foreignkey")
    op.create_foreign_key(
        FK_POINT_METRIC, "feedback_point", "metric_type",
        ["metric_type_id"], ["metric_type_id"],
    )


def downgrade() -> None:
    op.drop_constraint(FK_POINT_METRIC, "feedback_point", type_="foreignkey")
    op.create_foreign_key(
        FK_POINT_METRIC, "feedback_point", "metric_type",
        ["metric_type_id"], ["metric_type_id"], ondelete="SET NULL",
    )
    op.drop_constraint(FK_FINDING_METRIC, "finding", type_="foreignkey")
    op.create_foreign_key(
        FK_FINDING_METRIC, "finding", "metric_type",
        ["metric_type_id"], ["metric_type_id"], ondelete="SET NULL",
    )

    op.drop_constraint(CK_FINDING_OFFSET, "finding", type_="check")

    op.drop_constraint(UQ_TURN, "turn", type_="unique")
    op.drop_constraint(UQ_MEASUREMENT, "measurement", type_="unique")
