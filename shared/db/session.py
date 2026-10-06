"""Engine and session factory. The URL is read on first use, never at import."""
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import URL, Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from shared.env import optional, required

# `postgres://` and `postgresql://` both work; this is the one driver installed.
DRIVER = "postgresql+psycopg"

# Taken by every provisioning process. Migrating and seeding take it one after
# the other, never nested: holding it across both would deadlock the process.
PROVISION_LOCK_KEY = 8_243_119

POOL_SIZE = 5
POOL_MAX_OVERFLOW = 5
POOL_RECYCLE_SECONDS = 1800
CONNECT_TIMEOUT_SECONDS = 5


def build_database_url() -> URL:
    """`POSTGRES_URL`, with its password replaced by `POSTGRES_PASSWORD` if set."""
    url = make_url(required("POSTGRES_URL")).set(drivername=DRIVER)
    password = optional("POSTGRES_PASSWORD")
    return url.set(password=password) if password is not None else url


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(
        build_database_url(),
        pool_pre_ping=True,
        pool_size=POOL_SIZE,
        max_overflow=POOL_MAX_OVERFLOW,
        pool_recycle=POOL_RECYCLE_SECONDS,
        # A database that accepts TCP but never answers would hold a thread for minutes.
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
    )


@lru_cache(maxsize=1)
def _session_factory() -> sessionmaker[DbSession]:  # pylint: disable=unsubscriptable-object
    # The disable is a pylint blind spot: sessionmaker is generic only when type-checking.
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def reset_engine() -> None:
    """For tests switching databases. Disposed first: pooled connections block DROP DATABASE."""
    # pylint blind spot: it misreads lru_cache's cache_clear/cache_info here.
    if get_engine.cache_info().currsize:  # pylint: disable=too-many-function-args
        get_engine().dispose()
    get_engine.cache_clear()
    _session_factory.cache_clear()


@contextmanager
def session_scope() -> Iterator[DbSession]:
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
    """Serialises work across processes on a connection of its own."""
    with get_engine().connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": key})
        connection.commit()
        try:
            yield
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
            connection.commit()
