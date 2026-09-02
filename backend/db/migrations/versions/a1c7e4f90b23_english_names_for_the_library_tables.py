"""Rename the library tables and their columns from German to English

Revision ID: a1c7e4f90b23
Revises: b3f2a91c04de

Scope is the four reference tables the library is made of -- persona,
persona_einwand, szenario, sprache. The Session and Feedback tables of
ADR 0026/0051 keep their German names for now, so `session` stays internally
consistent (`szenario_id` next to `oeffentliche_id` and `gestartet_am`) rather
than becoming half-translated. Its foreign keys follow the renames on their
own: Postgres tracks constraints by identity, not by name.

Pure renames -- no column is added, dropped or retyped, so no data moves and
no backfill is needed. Unique constraints and indexes ride along with their
columns; only their generated *names* still mention the old spelling, which is
cosmetic and left alone rather than churned.

Written by hand: autogenerate cannot see a rename. It would emit a drop and a
create for every column here, which would silently discard the seeded library.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a1c7e4f90b23"
down_revision: Union[str, None] = "b3f2a91c04de"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, [(old column, new column)]) -- applied after the table rename below.
_COLUMNS = {
    "language": [("sprache_code", "code"), ("bezeichnung", "label")],
    "persona": [
        ("schluessel", "key"),
        ("rolle_anzeige", "role_label"),
        ("rolle", "role"),
        ("haltung", "traits"),
        ("verhalten", "behavior"),
        ("trainingsziel", "training_goal"),
        ("schwierigkeitsgrad", "difficulty"),
        ("aktiv", "active"),
        ("sprache_code", "language_code"),
        ("tts_stimme", "tts_voice"),
        ("kugelaudio_stimme_id", "kugelaudio_voice_id"),
    ],
    "persona_objection": [("einwand_id", "objection_id"), ("reihenfolge", "sort_order")],
    "scenario": [
        ("szenario_id", "scenario_id"),
        ("schluessel", "key"),
        ("typ", "type"),
        ("titel", "title"),
        ("kurzbeschreibung", "short_description"),
        ("beschreibung", "description"),
        ("fallfakten", "case_facts"),
        ("anrufziel", "call_goal"),
        ("erfolgsbedingung", "success_condition"),
    ],
}

_TABLES = [("sprache", "language"), ("szenario", "scenario"),
           ("persona_einwand", "persona_objection")]


def upgrade() -> None:
    for old, new in _TABLES:
        op.rename_table(old, new)
    for table, columns in _COLUMNS.items():
        for old, new in columns:
            op.alter_column(table, old, new_column_name=new)


def downgrade() -> None:
    for table, columns in _COLUMNS.items():
        for old, new in columns:
            op.alter_column(table, new, new_column_name=old)
    for old, new in reversed(_TABLES):
        op.rename_table(new, old)
