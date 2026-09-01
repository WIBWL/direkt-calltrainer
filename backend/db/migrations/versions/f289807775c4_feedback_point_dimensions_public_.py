"""Feedback point dimensions, public session id, nullable turn duration and befund offset

Revision ID: f289807775c4
Revises: 9008fded73e9
Create Date: 2026-08-31 16:35:25.457343

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f289807775c4'
down_revision: Union[str, None] = '9008fded73e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Constraints werden benannt statt von Alembic automatisch benennen zu lassen:
# ein unbenanntes Constraint laesst sich in downgrade() nicht wieder aufloesen.
FK_FEEDBACKPUNKT_METRIK_TYP = "fk_feedbackpunkt_metrik_typ_id"
UQ_SESSION_OEFFENTLICHE_ID = "uq_session_oeffentliche_id"


def upgrade() -> None:
    # Lockerungen zuerst -- sie koennen nicht fehlschlagen.
    # Nur Nutzer-Turns werden gemessen (ADR 0046), und ein Befund ueber die
    # ganze Aeusserung hat keine Position darin.
    op.alter_column("turn", "dauer_ms", existing_type=sa.INTEGER(), nullable=True)
    op.alter_column("befund", "offset_ms", existing_type=sa.INTEGER(), nullable=True)

    # Die neuen Spalten sind NOT NULL, die Tabellen koennen aber bereits Zeilen
    # enthalten. Daher dreistufig: nullable anlegen -> befuellen -> NOT NULL.
    op.add_column("feedbackpunkt", sa.Column("metrik_typ_id", sa.Integer(), nullable=True))
    op.add_column("feedbackpunkt", sa.Column("art", sa.String(length=20), nullable=True))
    op.add_column("feedbackpunkt", sa.Column("reihenfolge", sa.Integer(), nullable=True))
    op.create_foreign_key(
        FK_FEEDBACKPUNKT_METRIK_TYP, "feedbackpunkt", "metrik_typ",
        ["metrik_typ_id"], ["metrik_typ_id"],
    )

    # Bestandszeilen gelten als Verbesserungsvorschlag (F-10): das war die
    # einzige Art von Feedbackpunkt, die es vor dieser Migration gab.
    op.execute("UPDATE feedbackpunkt SET art = 'verbesserung' WHERE art IS NULL")
    # Reihenfolge je Feedback aus der bisherigen Einfuegereihenfolge ableiten,
    # damit die Anzeige stabil bleibt.
    op.execute(
        """
        UPDATE feedbackpunkt AS f
           SET reihenfolge = nummeriert.rang
          FROM (
                SELECT feedbackpunkt_id,
                       ROW_NUMBER() OVER (PARTITION BY feedback_id
                                              ORDER BY feedbackpunkt_id) - 1 AS rang
                  FROM feedbackpunkt
               ) AS nummeriert
         WHERE f.feedbackpunkt_id = nummeriert.feedbackpunkt_id
           AND f.reihenfolge IS NULL
        """
    )
    op.alter_column("feedbackpunkt", "art", existing_type=sa.String(length=20), nullable=False)
    op.alter_column("feedbackpunkt", "reihenfolge", existing_type=sa.INTEGER(), nullable=False)

    # gen_random_uuid() ist seit Postgres 13 eingebaut (compose.yaml: postgres:17).
    op.add_column("session", sa.Column("oeffentliche_id", sa.Uuid(), nullable=True))
    op.execute("UPDATE session SET oeffentliche_id = gen_random_uuid() WHERE oeffentliche_id IS NULL")
    op.alter_column("session", "oeffentliche_id", existing_type=sa.Uuid(), nullable=False)
    op.create_unique_constraint(UQ_SESSION_OEFFENTLICHE_ID, "session", ["oeffentliche_id"])


def downgrade() -> None:
    op.drop_constraint(UQ_SESSION_OEFFENTLICHE_ID, "session", type_="unique")
    op.drop_column("session", "oeffentliche_id")

    op.drop_constraint(FK_FEEDBACKPUNKT_METRIK_TYP, "feedbackpunkt", type_="foreignkey")
    op.drop_column("feedbackpunkt", "reihenfolge")
    op.drop_column("feedbackpunkt", "art")
    op.drop_column("feedbackpunkt", "metrik_typ_id")

    # Zurueck auf NOT NULL: Zeilen ohne Wert wuerden das verhindern, deshalb
    # vorher auffuellen. 0 heisst hier "unbekannt" -- genau der Zustand, den
    # diese Migration ueberhaupt erst als NULL ausdrueckbar gemacht hat.
    op.execute("UPDATE befund SET offset_ms = 0 WHERE offset_ms IS NULL")
    op.execute("UPDATE turn SET dauer_ms = 0 WHERE dauer_ms IS NULL")
    op.alter_column("befund", "offset_ms", existing_type=sa.INTEGER(), nullable=False)
    op.alter_column("turn", "dauer_ms", existing_type=sa.INTEGER(), nullable=False)
