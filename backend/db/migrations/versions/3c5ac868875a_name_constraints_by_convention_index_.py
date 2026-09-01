"""Name constraints by convention, index foreign keys, constrain vocabularies

Revision ID: 3c5ac868875a
Revises: 6269b27b75f9
Create Date: 2026-09-01

Three things at once, because they are one change in intent: make the schema
say what it means and enforce it.

1. Every constraint is renamed to the naming convention now set on
   Base.metadata. Autogenerate could not do this — it compares structure, not
   names — but from here on it emits these names by itself, which is what stops
   it producing the unnamed constraints whose downgrade cannot run.
2. Every foreign-key column gets an index. Postgres only indexes the referenced
   side, so deleting a Session was scanning each child table sequentially.
3. The enum-like columns get CHECK constraints. Alembic does not autodetect
   these, so they are written out below.

The renames identify each constraint by its *structure* — table, kind, column —
rather than by its current name, because that name depends on when the database
was created. Introducing a naming convention changes what the earlier revisions
produce: a database migrated before this revision has Postgres' default names
("analysis_job_pkey"), while one created afterwards already gets convention
names derived from the table names of the time ("pk_szenario", before the
German-to-English rename). Matching on structure converges both onto the same
result and makes this revision safe to re-run.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '3c5ac868875a'
down_revision: Union[str, None] = '6269b27b75f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PRIMARY_KEYS = [
    "analysis_job", "feedback", "feedback_point", "finding", "language",
    "measurement", "metric_type", "persona", "persona_objection", "scenario",
    "session", "turn",
]

# (table, column, new_name) for single-column unique constraints.
UNIQUES = [
    ("feedback", "session_id", "uq_feedback_session_id"),
    ("metric_type", "key", "uq_metric_type_key"),
    ("persona", "key", "uq_persona_key"),
    ("scenario", "key", "uq_scenario_key"),
    ("session", "extern_id", "uq_session_extern_id"),
]

# (table, column, new_name) — every foreign key here is single-column.
FOREIGN_KEYS = [
    ("analysis_job", "session_id", "fk_analysis_job_session_id_session"),
    ("feedback", "session_id", "fk_feedback_session_id_session"),
    ("feedback_point", "feedback_id", "fk_feedback_point_feedback_id_feedback"),
    ("feedback_point", "finding_id", "fk_feedback_point_finding_id_finding"),
    ("feedback_point", "turn_id", "fk_feedback_point_turn_id_turn"),
    ("finding", "metric_type_id", "fk_finding_metric_type_id_metric_type"),
    ("finding", "turn_id", "fk_finding_turn_id_turn"),
    ("measurement", "metric_type_id", "fk_measurement_metric_type_id_metric_type"),
    ("measurement", "turn_id", "fk_measurement_turn_id_turn"),
    ("persona", "language_code", "fk_persona_language_code_language"),
    ("persona_objection", "persona_id", "fk_persona_objection_persona_id_persona"),
    ("session", "language_code", "fk_session_language_code_language"),
    ("session", "persona_id", "fk_session_persona_id_persona"),
    ("session", "scenario_id", "fk_session_scenario_id_scenario"),
    ("turn", "session_id", "fk_turn_session_id_session"),
]

# (table, column) — one index per foreign-key column.
FK_INDEXES = [(table, column) for table, column, _ in FOREIGN_KEYS]

# (table, constraint_name_without_prefix, condition)
CHECKS = [
    ("session", "status_valid", "status IN ('completed', 'aborted')"),
    ("analysis_job", "kind_valid", "kind IN ('analysis', 'feedback')"),
    ("analysis_job", "status_valid", "status IN ('queued', 'running', 'done', 'failed')"),
    ("turn", "seq_index_positive", "seq_index >= 1"),
    ("turn", "user_duration_non_negative", "user_duration_ms IS NULL OR user_duration_ms >= 0"),
    ("turn", "persona_duration_non_negative", "persona_duration_ms IS NULL OR persona_duration_ms >= 0"),
]


def _rename(table: str, contype: str, new_name: str, column: str | None = None) -> None:
    """Renames the constraint of kind `contype` on `table` — identified by
    `column` where given — to `new_name`, whatever it is called right now.

    A no-op when it already carries that name, so the revision is re-runnable.
    """
    column_match = (
        f"""AND c.conkey = ARRAY[(SELECT a.attnum FROM pg_attribute a
                 WHERE a.attrelid = c.conrelid AND a.attname = '{column}')::smallint]"""
        if column
        else ""
    )
    op.execute(
        f"""
        DO $$
        DECLARE current_name text;
        BEGIN
            SELECT c.conname INTO current_name
              FROM pg_constraint c
             WHERE c.conrelid = '{table}'::regclass
               AND c.contype = '{contype}'
               {column_match};
            IF current_name IS NOT NULL AND current_name <> '{new_name}' THEN
                EXECUTE format('ALTER TABLE {table} RENAME CONSTRAINT %I TO %I',
                               current_name, '{new_name}');
            END IF;
        END $$;
        """
    )


def _index_name(table: str, column: str) -> str:
    """Matches the "ix" rule of the naming convention in backend/db/base.py."""
    return f"ix_{table}_{column}"


def upgrade() -> None:
    """Renames constraints, indexes the foreign keys, adds the CHECKs."""
    for table in PRIMARY_KEYS:
        _rename(table, "p", f"pk_{table}")
    for table, column, new_name in UNIQUES:
        _rename(table, "u", new_name, column)
    for table, column, new_name in FOREIGN_KEYS:
        _rename(table, "f", new_name, column)

    for table, column in FK_INDEXES:
        op.create_index(_index_name(table, column), table, [column], unique=False)

    for table, name, condition in CHECKS:
        op.create_check_constraint(name, table, sa.text(condition))


# The three constraints that earlier revisions drop *by name* in their own
# downgrade. Those names have to exist again before this revision hands back
# control, or the chain breaks halfway down. Every other constraint is only
# ever dropped along with its table or column, so its name does not matter.
# (table, contype, column, name expected further down the chain)
DOWNGRADE_NAMES = [
    ("persona", "u", "key", "uq_persona_schluessel"),          # 9008fded73e9
    ("scenario", "u", "key", "uq_szenario_schluessel"),        # 9008fded73e9
    ("persona", "f", "language_code", "persona_sprache_code_fkey"),  # e8ee215bf9bf
]


def downgrade() -> None:
    """Drops what upgrade added and restores the names earlier revisions expect.

    Column and table names are still English at this point — the German rename
    is undone by the revision below this one, which runs afterwards.
    """
    for table, name, _ in CHECKS:
        # The short name, not the expanded one: the naming convention is applied
        # to drop_constraint as well, so passing "ck_session_status_valid" here
        # would ask Postgres for "ck_session_ck_session_status_valid".
        op.drop_constraint(name, table, type_="check")

    for table, column in FK_INDEXES:
        op.drop_index(_index_name(table, column), table_name=table)

    for table, contype, column, name in DOWNGRADE_NAMES:
        _rename(table, contype, name, column)
