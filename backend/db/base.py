"""Declarative base for all ORM entities.

Its own module so models, session and Alembic import it without cycles (ADR 0025).
"""
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Deterministic constraint and index names (ADR 0053). Without them autogenerate
# emits unnamed constraints whose `drop_constraint(None, ...)` in downgrade()
# cannot run.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
