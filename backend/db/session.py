"""
Database access: engine and session factory.

Single entry point through which app and worker talk to Postgres. The
connection URL is assembled here from the POSTGRES_* settings and built on
first use, not at import time, so importing this module never requires a
loaded environment.
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

# Any process that provisions the database takes this lock first, so the app
# and the worker starting together serialise instead of racing. Held by one
# process at a time and never nested, so migrating and seeding can share it:
# each acquires it, finishes, and releases before the other step begins.
PROVISION_LOCK_KEY = 8_243_119

POOL_SIZE = 5
POOL_MAX_OVERFLOW = 5
POOL_RECYCLE_SECONDS = 1800
CONNECT_TIMEOUT_SECONDS = 5


def build_database_url() -> URL:
    """Assembles the connection URL from the POSTGRES_* settings.

    Kept out of the environment as a ready-made DATABASE_URL: it would only
    repeat user, password and database name that are already configured
    separately, and a URL duplicated across .env and compose.yaml is one more
    place for the password to drift out of sync.

    SQLAlchemy's URL.create quotes the components, so a password containing
    "@", "/" or "%" needs no manual escaping.

    Read here rather than at import time so that importing this module -- which
    models.py and the migrations do -- never requires an environment.
    """
    missing = [
        k for k in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB")
        if not os.environ.get(k)
    ]
    if missing:
        raise RuntimeError(
            f"Database settings missing: {', '.join(missing)}. Inside the container "
            "they come from the env_file (.env); locally, call load_dotenv() first."
        )
    return URL.create(
        "postgresql+psycopg",
        username=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        # `or`, not a get() default: an .env that names the variable without
        # a value ("POSTGRES_PORT=") yields "", which is not missing as far as
        # get() is concerned -- and int("") then raises where the check above
        # would have said what was wrong.
        host=os.environ.get("POSTGRES_HOST") or DEFAULT_HOST,
        port=int(os.environ.get("POSTGRES_PORT") or DEFAULT_PORT),
        database=os.environ["POSTGRES_DB"],
    )


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """The process-wide engine, created on first call.

    The pool is sized for what actually competes for it: FastAPI's threadpool
    running the sync `def` endpoints, plus the single `asyncio.to_thread` call
    that writes a finished Session. That is a handful of connections, not one
    per concurrent call — nothing holds a connection while a Session is live.
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
    """Discards the cached engine and session factory.

    The engine is built once and memoised, which is what a long-running process
    wants — but it also means a later change to the POSTGRES_* settings has no
    effect. Tests use this to point the application at their own throwaway
    database; nothing in the running application calls it.

    Disposed before it is forgotten: an engine that is merely unreferenced
    keeps its pooled connections open until it is collected, and those hold
    open the database a test is about to drop.
    """
    # The disables are the same pylint blind spot as above: calling the
    # memoised function in this block makes it lose track of lru_cache's
    # wrapper, and it then reads the no-argument cache_clear() as a call with
    # too many arguments.
    if get_engine.cache_info().currsize:  # pylint: disable=too-many-function-args
        get_engine().dispose()
    get_engine.cache_clear()  # pylint: disable=too-many-function-args
    _session_factory.cache_clear()


@contextmanager
def session_scope() -> Iterator[DbSession]:
    """Session with automatic commit / rollback / close.

    Usage:
        with session_scope() as db:
            db.add(obj)
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

    A Postgres advisory lock belongs to the session that took it, so this holds
    one connection for the duration. The commit right after acquiring matters:
    the execute opened a transaction, and leaving it open would put the caller
    inside it. The lock is session-scoped and outlives that commit.
    """
    with get_engine().connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": key})
        connection.commit()
        try:
            yield
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
            connection.commit()
