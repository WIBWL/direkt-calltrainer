"""Database access: engine and session factory, for app and worker alike.

The URL is read on first use, not at import time, so importing this module
never requires a configured environment.
"""
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import URL, Engine, create_engine, text
from sqlalchemy.engine import make_url
# Aliased because "Session" is also an entity of this schema (models.Session).
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from shared.env import optional, required

# The one driver installed; `postgres://` and `postgresql://` are accepted for
# the same database, so a URL written for any other client works here too.
DRIVER = "postgresql+psycopg"

# Taken by every process that provisions the database (app instances,
# backend/scripts/seed_reference_data.py), so they serialise instead of racing; the
# worker migrates nothing. Migrating and seeding share it because it is never
# nested: each step acquires and releases it before the next begins. Holding it
# across both would make the process wait on itself, with no timeout.
PROVISION_LOCK_KEY = 8_243_119

POOL_SIZE = 5
POOL_MAX_OVERFLOW = 5
POOL_RECYCLE_SECONDS = 1800
CONNECT_TIMEOUT_SECONDS = 5


def build_database_url() -> URL:
    """The connection URL: `POSTGRES_URL`, whose password `POSTGRES_PASSWORD`
    replaces when set. A deployment keeps the password in one Docker secret that
    the database container reads too (`POSTGRES_PASSWORD_FILE`), and names the
    rest in the URL; in development the URL carries it and nothing else is set.
    """
    url = make_url(required("POSTGRES_URL")).set(drivername=DRIVER)
    password = optional("POSTGRES_PASSWORD")
    # URL.set quotes the components, so "@", "/" or "%" in it need no escaping.
    return url.set(password=password) if password is not None else url


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
