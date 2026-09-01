import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool, text

# pylint: disable=wrong-import-position  # sys.path has to be set up first
# Make the project root importable ("backend.db...") and load .env for the
# POSTGRES_* settings the connection URL is assembled from.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from backend.db.models import Base  # noqa: E402
from backend.db.session import build_database_url  # noqa: E402

config = context.config

try:
    # Same assembly the application uses, so migrations can never run against a
    # different database than the app does.
    DATABASE_URL = build_database_url().render_as_string(hide_password=False)
except RuntimeError as exc:
    raise SystemExit(
        f"{exc} See .env.example for the POSTGRES_* settings."
    ) from exc
# Doubled because alembic.ini is read through ConfigParser, where a single "%"
# starts an interpolation and would reject a password containing one.
config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Autogenerate diffs the models against the database (ADR 0027).
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Render the migrations as SQL, without connecting to a database."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


# Arbitrary but fixed: any process migrating this schema uses the same key, so
# two of them serialise instead of racing. Postgres advisory locks are scoped to
# the database, so a test's throwaway database never blocks the real one.
MIGRATION_LOCK_KEY = 8_243_119


def run_migrations_online() -> None:
    """Run the migrations against a live database.

    Guarded by an advisory lock: docker-entrypoint.sh migrates on every
    container start, so scaling to more than one instance would otherwise have
    them apply the same revision concurrently. The second one waits here and
    then finds nothing left to do.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": MIGRATION_LOCK_KEY})
        # Committed straight away: the execute above opened a transaction, and
        # leaving it open would swallow Alembic's own, rolling the migrations
        # back at the end. The lock is session-scoped and outlives the commit.
        connection.commit()
        try:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": MIGRATION_LOCK_KEY})
            connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
