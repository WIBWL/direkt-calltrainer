"""Measurements per segment of a call, and the raw facts to compute them from

Revision ID: f3a5c81be47d
Revises: d4c81b70e2a5

ADR 0081. "Souveränität unter Druck" (F-62) is the focus goal nothing could be
measured for: it asks how the trainee's delivery holds up in the demanding
stretches of a call, and the schema only ever held one figure for the whole of
it.

Three columns:

`measurement.segment` says which stretch a figure describes -- `call` for the
whole of it, `pressure` for the exchanges the wrap-up marked as demanding,
`rest` for the remainder. NOT NULL with a real value for the whole call rather
than a nullable column, because the unique constraint below has to keep
covering the whole-call rows and Postgres treats two NULLs as distinct. Existing
rows are backfilled to `call`, which is exactly what they are: the column adds
a name for something that was already true.

`turn.acoustics_json` keeps the raw paraverbal facts of one user utterance --
speaking time, phonation, pauses, its stretch of the loudness curve. It is the
exception ADR 0081 takes to ADR 0051 and it is narrow: raw facts, never a
statistic, never shown. It exists because the audio is discarded when the call
ends (ADR 0048) while *which* stretch was demanding is decided afterwards by the
wrap-up, so without it there would be nothing left to measure by then. NULL on
Persona rows and on every call recorded before this.

`turn.pressed` is that decision, on the Persona rows. NULL means nobody has
judged the row yet, which is deliberately not False.

The unique constraint is widened from (session, metric) to (session, metric,
segment). It keeps its name, since the convention names it after the first
column. Dropped and recreated rather than altered, which is the only way in
Postgres.

Nothing is backfilled beyond the segment name. A stored Session has no per-turn
acoustics and never will -- its audio is gone -- so it keeps its whole-call
figures and gains no segment rows, and the interface says so rather than
showing an empty block.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f3a5c81be47d"
down_revision: Union[str, None] = "d4c81b70e2a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The convention names a unique constraint after its first column, so widening
# it does not rename it.
UQ_MEASUREMENT = "uq_measurement_session_id"


def upgrade() -> None:
    op.add_column(
        "turn", sa.Column("acoustics_json", postgresql.JSONB(), nullable=True)
    )
    op.add_column("turn", sa.Column("pressed", sa.Boolean(), nullable=True))

    # Added nullable, filled, then pinned: a NOT NULL column added outright
    # fails on a populated table, and this one is populated everywhere the
    # application runs.
    op.add_column("measurement", sa.Column("segment", sa.String(20), nullable=True))
    op.execute("UPDATE measurement SET segment = 'call' WHERE segment IS NULL")
    op.alter_column("measurement", "segment", nullable=False)

    op.drop_constraint(UQ_MEASUREMENT, "measurement", type_="unique")
    op.create_unique_constraint(
        UQ_MEASUREMENT, "measurement", ["session_id", "metric_type_id", "segment"]
    )
    # Alembic does not autodetect CHECK constraints; this one is written by
    # hand, and passes the bare name because op.* applies the convention itself.
    op.create_check_constraint(
        "segment_valid", "measurement", "segment IN ('call', 'pressure', 'rest')"
    )


def downgrade() -> None:
    # The segment rows go first. Without that the narrowed constraint cannot be
    # created: two rows differing only in segment are a duplicate under it.
    op.execute("DELETE FROM measurement WHERE segment <> 'call'")

    op.drop_constraint(
        op.f("ck_measurement_segment_valid"), "measurement", type_="check"
    )
    op.drop_constraint(UQ_MEASUREMENT, "measurement", type_="unique")
    op.create_unique_constraint(
        UQ_MEASUREMENT, "measurement", ["session_id", "metric_type_id"]
    )
    op.drop_column("measurement", "segment")

    op.drop_column("turn", "pressed")
    op.drop_column("turn", "acoustics_json")
