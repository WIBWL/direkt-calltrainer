"""Measurements and findings describe the Session, not a single Turn

Revision ID: b4e1a72c9d05
Revises: f289807775c4
Create Date: 2026-08-31 19:40:11.204418

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4e1a72c9d05'
down_revision: Union[str, None] = 'f289807775c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Constraints werden benannt statt von Alembic automatisch benennen zu lassen:
# ein unbenanntes Constraint laesst sich in downgrade() nicht wieder aufloesen.
FK_MESSUNG_SESSION = "fk_messung_session_id"
FK_BEFUND_SESSION = "fk_befund_session_id"
FK_MESSUNG_TURN = "fk_messung_turn_id"
FK_BEFUND_TURN = "fk_befund_turn_id"


def upgrade() -> None:
    # ADR 0051: Kennzahlen beschreiben das ganze Gespraech. Messung und Befund
    # haengen deshalb an der Session statt an einem einzelnen Turn.
    #
    # Dreistufig, weil die Tabellen bereits Zeilen enthalten koennen: Spalte
    # nullable anlegen -> aus dem bisherigen Turn befuellen -> NOT NULL.
    for tabelle, constraint in (("messung", FK_MESSUNG_SESSION), ("befund", FK_BEFUND_SESSION)):
        op.add_column(tabelle, sa.Column("session_id", sa.Integer(), nullable=True))
        op.execute(
            f"UPDATE {tabelle} AS z"
            "   SET session_id = t.session_id"
            "  FROM turn AS t"
            " WHERE t.turn_id = z.turn_id"
        )
        # Waisen kann es nicht geben (turn_id war NOT NULL mit Fremdschluessel),
        # daher ist die Spalte hier vollstaendig befuellt.
        op.alter_column(tabelle, "session_id", existing_type=sa.INTEGER(), nullable=False)
        op.create_foreign_key(constraint, tabelle, "session", ["session_id"], ["session_id"])
        # Postgres loescht die Fremdschluessel der Spalte gleich mit.
        op.drop_column(tabelle, "turn_id")


def downgrade() -> None:
    # Verlustbehaftet: die Zuordnung auf einen einzelnen Turn existiert nicht
    # mehr. Jede Zeile faellt auf den ersten Turn ihrer Session zurueck -- das
    # ist die einzige Zuordnung, die ohne die geloeschte Spalte noch definiert
    # ist. Zeilen von Sessions ohne Turn koennen nicht zurueckgebildet werden.
    for tabelle, constraint in (("messung", FK_MESSUNG_TURN), ("befund", FK_BEFUND_TURN)):
        op.add_column(tabelle, sa.Column("turn_id", sa.Integer(), nullable=True))
        op.execute(
            f"UPDATE {tabelle} AS z"
            "   SET turn_id = ("
            "       SELECT t.turn_id FROM turn AS t"
            "        WHERE t.session_id = z.session_id"
            "        ORDER BY t.seq_index, t.turn_id"
            "        LIMIT 1)"
        )
        if tabelle == "befund":
            # Feedbackpunkte zeigen auf Befunde; die Zitate muessen geloest
            # werden, bevor die nicht zurueckbildbaren Zeilen verschwinden.
            op.execute(
                "UPDATE feedbackpunkt SET befund_id = NULL"
                " WHERE befund_id IN (SELECT befund_id FROM befund WHERE turn_id IS NULL)"
            )
        op.execute(f"DELETE FROM {tabelle} WHERE turn_id IS NULL")
        op.alter_column(tabelle, "turn_id", existing_type=sa.INTEGER(), nullable=False)
        op.create_foreign_key(constraint, tabelle, "turn", ["turn_id"], ["turn_id"])
        op.drop_column(tabelle, "session_id")
