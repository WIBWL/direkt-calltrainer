import logging
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

from shared.db.models import Base
from shared.db.session import PROVISION_LOCK_KEY, build_database_url

config = context.config

try:
    # The app's own URL builder, so migrations hit the app's database.
    DATABASE_URL = build_database_url().render_as_string(hide_password=False)
except RuntimeError as exc:
    raise SystemExit(
        f"{exc} -- `source .env` first."
    ) from exc
# Doubled: ConfigParser treats "%" as interpolation.
config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))

# fileConfig() disables existing loggers; the app's in-process migration opts out.
if config.config_file_name is not None and config.attributes.get("configure_logging", True):
    fileConfig(config.config_file_name)

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


# Shared with seeding (backend/db/provision.py); scoped to the database.
MIGRATION_LOCK_KEY = PROVISION_LOCK_KEY


def run_migrations_online() -> None:
    """Under an advisory lock, so concurrent boots never apply a revision twice."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        # Announced first: pg_advisory_lock blocks with no deadline or output.
        logging.getLogger("alembic.runtime.migration").info(
            "Waiting for the migration advisory lock"
        )
        connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": MIGRATION_LOCK_KEY})
        # Commit now, or Alembic's transaction is swallowed and rolled back.
        # The lock is session-scoped and survives the commit.
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
