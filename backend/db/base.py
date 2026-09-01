"""
Declarative base for all ORM entities.

Kept in its own module so that models, session and Alembic can import it
independently, without import cycles (ADR 0025).
"""
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Every constraint and index gets a deterministic name derived from the table
# and column it belongs to. Without this, Postgres invents the names and
# autogenerate emits `create_unique_constraint(None, ...)` /
# `create_foreign_key(None, ...)`, whose matching `drop_constraint(None, ...)`
# in downgrade() cannot run — a broken downgrade in every revision that adds a
# constraint. The convention is the one SQLAlchemy and Alembic both document.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
