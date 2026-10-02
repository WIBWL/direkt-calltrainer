"""Database access: engine and session factory, for app and worker alike.

The URL is built from the POSTGRES_* settings on first use, not at import
time, so importing this module never requires a loaded environment.
"""
import os
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import URL, Engine, create_engine, text
# Aliased because "Session" is also an entity of this schema (models.Session).
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

# Host and port are the only part of the URL that differs between running on
# the host and running inside the compose network, where the database is
# reachable as "db" rather than on localhost.
DEFAULT_HOST = "localhost"
DEFAULT_PORT = "5432"

# The role and database the `db` service creates; overridable only so tests and
# scripts/stress_db.py can aim at a throwaway database. Not "postgres": existing
# volumes were initialised with "trainer", and Postgres applies the name only
# on first init, so renaming would point at a database that does not exist.
DEFAULT_USER = "trainer"
DEFAULT_DATABASE = "trainer"

# Taken by every process that provisions the database (app instances,
# scripts/seed_reference_data.py), so they serialise instead of racing; the
# worker migrates nothing. Migrating and seeding share it because it is never
# nested: each step acquires and releases it before the next begins. Holding it
# across both would make the process wait on itself, with no timeout.
PROVISION_LOCK_KEY = 8_243_119

POOL_SIZE = 5
POOL_MAX_OVERFLOW = 5
POOL_RECYCLE_SECONDS = 1800
CONNECT_TIMEOUT_SECONDS = 5


def build_database_url() -> URL:
    """Assembles the connection URL from the POSTGRES_* settings; only the
    password is required. No DATABASE_URL, so the password lives in one place.
    URL.create quotes the components, so "@", "/" or "%" need no escaping.
    """
    if not os.environ.get("POSTGRES_PASSWORD"):
        raise RuntimeError(
            "Database settings missing: POSTGRES_PASSWORD. Inside the container "
            "it comes from the env_file (.env); locally, call load_dotenv() first."
        )
    return URL.create(
        "postgresql+psycopg",
        # `or`, not a get() default: an .env that names the variable without
        # a value ("POSTGRES_PORT=") yields "", which is not missing as far as
        # get() is concerned -- and int("") would then raise.
        username=os.environ.get("POSTGRES_USER") or DEFAULT_USER,
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.environ.get("POSTGRES_HOST") or DEFAULT_HOST,
        port=int(os.environ.get("POSTGRES_PORT") or DEFAULT_PORT),
        database=os.environ.get("POSTGRES_DB") or DEFAULT_DATABASE,
    )


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """The process-wide engine, created on first call.

    A small pool suffices: only the sync endpoints and the post-call write use
    it, and nothing holds a connection while a Session is live.
    """
    return create_engine(
        build_database_url(),
        # Checks a connection before handing it out, so one dropped by a
        # restart or an idle timeout is replaced instead of raising.
        pool_pre_ping=True,
        pool_size=POOL_SIZE,
        max_overflow=POOL_MAX_OVERFLOW,
        # Retire connections well before any server- or firewall-side idle
        # timeout can silently kill them.
        pool_recycle=POOL_RECYCLE_SECONDS,
        # Without this a database that accepts TCP but never answers would hold
        # a threadpool thread until the OS gives up, minutes later.
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
    )


@lru_cache(maxsize=1)
def _session_factory() -> sessionmaker[DbSession]:  # pylint: disable=unsubscriptable-object
    """The process-wide session factory. The disable above is a pylint blind
    spot: sessionmaker is generic at type-check time but not at runtime."""
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def reset_engine() -> None:
    """Discards the cached engine and session factory, for tests that switch to
    a throwaway database. Disposed first: an unreferenced engine keeps its
    pooled connections open, which blocks dropping the test database.
    """
    # The disables are the same pylint blind spot as above: calling the
    # memoised function in this block makes it lose track of lru_cache's
    # wrapper, and it then reads the no-argument cache_clear() as a call with
    # too many arguments.
    if get_engine.cache_info().currsize:  # pylint: disable=too-many-function-args
        get_engine().dispose()
    get_engine.cache_clear()
    _session_factory.cache_clear()


@contextmanager
def session_scope() -> Iterator[DbSession]:
    """Session with automatic commit / rollback / close:
    `with session_scope() as db: db.add(obj)`.
    """
    db = _session_factory()()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def advisory_lock(key: int = PROVISION_LOCK_KEY) -> Iterator[None]:
    """Serialises a block of work across processes, on a connection of its own.

    The commit after acquiring closes the transaction the execute opened; the
    session-scoped lock outlives it.
    """
    with get_engine().connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": key})
        connection.commit()
        try:
            yield
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
            connection.commit()
