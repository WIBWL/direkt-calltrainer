"""Drop four covered indexes and rename the six sequences ADR 0057 left behind

Two leftovers of the same kind: the migrated database and one built from
models.py by create_all had drifted apart, which is the property every schema
test leans on.

The four indexes each sit on a column that a unique constraint already leads
with, so Postgres had two indexes on it and maintained both on every insert.
models.py argues exactly this case the other way at scenario.origin_session_id
(ADR 0052); test_every_foreign_key_column_is_indexed reads the leading column
of any index and is satisfied by the unique one.

The six sequences kept the German names SERIAL gave them before ADR 0057
renamed the tables and columns around them: renaming a table does not rename
its sequence. Nothing in the application addresses a sequence by name -- this
is for whoever restores a dump and calls setval.

Revision ID: c1a6b8407f52
Revises: a3f19c605e82
Create Date: 2026-09-12

"""
from alembic import op


revision = "c1a6b8407f52"
down_revision = "a3f19c605e82"
branch_labels = None
depends_on = None


# (index name, table, column) -- each column is the leading one of a unique
# constraint on the same table, which is what makes the index redundant.
COVERED_INDEXES = [
    ("ix_turn_session_id", "turn", "session_id"),
    ("ix_measurement_session_id", "measurement", "session_id"),
    ("ix_focus_selection_goal_selection_id",
     "focus_selection_goal", "selection_id"),
    ("ix_focus_selection_category_selection_id",
     "focus_selection_category", "selection_id"),
]

# (name a migrated database carries, name create_all produces)
SEQUENCE_RENAMES = [
    ("befund_befund_id_seq", "finding_finding_id_seq"),
    ("feedbackpunkt_feedbackpunkt_id_seq", "feedback_point_feedback_point_id_seq"),
    ("messung_messung_id_seq", "measurement_measurement_id_seq"),
    ("metrik_typ_metrik_typ_id_seq", "metric_type_metric_type_id_seq"),
    ("persona_einwand_einwand_id_seq", "persona_objection_objection_id_seq"),
    ("szenario_szenario_id_seq", "scenario_scenario_id_seq"),
]


def _rename_sequences(pairs) -> None:
    """IF EXISTS on both sides: a database built by create_all rather than by
    the migration chain already carries the English name, and the rename would
    otherwise fail there instead of finding nothing to do."""
    for old, new in pairs:
        op.execute(
            f"DO $$ BEGIN "
            f"IF EXISTS (SELECT 1 FROM pg_class WHERE relname = '{old}' "
            f"AND relkind = 'S') "
            f"AND NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = '{new}' "
            f"AND relkind = 'S') "
            f"THEN ALTER SEQUENCE {old} RENAME TO {new}; "
            f"END IF; END $$;"
        )


def upgrade() -> None:
    for name, table, _column in COVERED_INDEXES:
        op.drop_index(name, table_name=table)
    _rename_sequences(SEQUENCE_RENAMES)


def downgrade() -> None:
    _rename_sequences([(new, old) for old, new in SEQUENCE_RENAMES])
    for name, table, column in COVERED_INDEXES:
        op.create_index(name, table, [column])
