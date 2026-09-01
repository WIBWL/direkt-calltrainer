"""Enforce ownership deletes in the database

Revision ID: fa39923208c7
Revises: 3c5ac868875a
Create Date: 2026-09-01

Until now the delete cascades existed only in the ORM, so ADR 0034's promise
that a User can remove their own data held for `session.delete(obj)` and for
nothing else: a plain `DELETE FROM session` failed on a foreign-key violation.

Ownership edges now cascade in Postgres itself, and the two optional
back-references from a FeedbackPoint are set to NULL rather than removing a
point that still reads sensibly without its anchor. Foreign keys into the
reference tables (persona, scenario, language, metric_type on a Measurement)
deliberately keep NO ACTION: deleting a Persona that has stored Sessions should
fail, not quietly take those Sessions with it.

Hand-written because autogenerate does not compare a foreign key's ondelete
clause — it sees no difference and would emit an empty migration.
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'fa39923208c7'
down_revision: Union[str, None] = '3c5ac868875a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (constraint, table, column, referred table, referred column, ondelete)
FOREIGN_KEYS = [
    ("fk_analysis_job_session_id_session", "analysis_job", "session_id", "session", "session_id", "CASCADE"),
    ("fk_feedback_session_id_session", "feedback", "session_id", "session", "session_id", "CASCADE"),
    ("fk_feedback_point_feedback_id_feedback", "feedback_point", "feedback_id", "feedback", "feedback_id", "CASCADE"),
    ("fk_feedback_point_finding_id_finding", "feedback_point", "finding_id", "finding", "finding_id", "SET NULL"),
    ("fk_feedback_point_turn_id_turn", "feedback_point", "turn_id", "turn", "turn_id", "SET NULL"),
    ("fk_finding_metric_type_id_metric_type", "finding", "metric_type_id", "metric_type", "metric_type_id", "SET NULL"),
    ("fk_finding_turn_id_turn", "finding", "turn_id", "turn", "turn_id", "CASCADE"),
    ("fk_measurement_turn_id_turn", "measurement", "turn_id", "turn", "turn_id", "CASCADE"),
    ("fk_persona_objection_persona_id_persona", "persona_objection", "persona_id", "persona", "persona_id", "CASCADE"),
    ("fk_turn_session_id_session", "turn", "session_id", "session", "session_id", "CASCADE"),
]


def upgrade() -> None:
    """Adds the ondelete clause each foreign key is declared with.

    Postgres cannot alter an existing foreign key's ondelete, so each one is
    dropped and rebuilt. That is metadata-only — no table is rewritten.
    """
    for name, table, column, ref_table, ref_column, ondelete in FOREIGN_KEYS:
        op.drop_constraint(name, table, type_="foreignkey")
        op.create_foreign_key(
            name, table, ref_table, [column], [ref_column], ondelete=ondelete
        )


def downgrade() -> None:
    """Back to NO ACTION, which is what omitting ondelete means."""
    for name, table, column, ref_table, ref_column, _ in FOREIGN_KEYS:
        op.drop_constraint(name, table, type_="foreignkey")
        op.create_foreign_key(name, table, ref_table, [column], [ref_column])
