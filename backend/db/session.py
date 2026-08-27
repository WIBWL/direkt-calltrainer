"""
Database access: engine and session factory.

Single entry point through which app and worker talk to Postgres. The
connection URL comes from DATABASE_URL and is read on first use, not at
import time, so importing this module never requires a loaded environment.
"""
import os
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
# Aliased because "Session" is also an entity of this schema (models.Session).
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """The process-wide engine, created on first call."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Inside the container it comes from the "
            "env_file (.env); locally, call load_dotenv() first."
        )
    # pool_pre_ping checks a connection before use -> no stale connections.
    return create_engine(url, pool_pre_ping=True)


@lru_cache(maxsize=1)
def _session_factory() -> sessionmaker[DbSession]:  # pylint: disable=unsubscriptable-object
    """The process-wide session factory. The disable above is a pylint blind
    spot: sessionmaker is generic at type-check time but not at runtime."""
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


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
