"""The database both processes share."""

from pathlib import Path

ALEMBIC_INI = Path(__file__).resolve().parent / "alembic.ini"
