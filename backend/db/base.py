"""
Declarative base for all ORM entities.

Kept in its own module so that models, session and Alembic can import it
independently, without import cycles (ADR 0025).
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
