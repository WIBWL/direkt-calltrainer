"""The database both processes share: the models, the session, the seed data and
the migrations that build the schema (the backend runs them at boot)."""

from pathlib import Path

# Beside the migrations it configures, so it resolves from any working directory.
ALEMBIC_INI = Path(__file__).resolve().parent / "alembic.ini"
