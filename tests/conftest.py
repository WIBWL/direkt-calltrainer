"""Shared fixtures for the database tests.

Every test that needs a database gets its own, created fresh and dropped
afterwards, so a failing test can never leave the development database in a
half-migrated state and tests cannot see each other's rows. That costs a few
hundred milliseconds per test and buys complete isolation.

The connection details come from the same POSTGRES_* settings the application
uses, but only the server part of them: the database name is replaced with a
generated one. Without those settings, or without a reachable server, these
tests skip rather than fail, so a checkout without Postgres running still gets
a green run of everything else.
"""
import os
import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from backend.db.models import Language, MetricType, Persona, Scenario
from backend.db.session import build_database_url, reset_engine
from backend.session.models import FinishedSession, Turn

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def _render(url: URL) -> str:
    """URL.__str__ masks the password, which makes the result unusable as a
    connection string — this keeps it."""
    return url.render_as_string(hide_password=False)


def _server_url() -> URL:
    """The configured database server, or a skip if the settings are incomplete."""
    try:
        return build_database_url()
    except RuntimeError as exc:
        # `return` only so every path returns an expression: skip() raises.
        return pytest.skip(f"Database settings incomplete: {exc}")


@contextmanager
def database_env(url: str) -> Iterator[None]:
    """Points POSTGRES_DB at the database in `url` for the duration of the block.

    Alembic's env.py and the seed script both assemble their connection from
    the POSTGRES_* settings, so overriding the database name is how a test aims
    them at its own throwaway database.
    """
    name = make_url(url).database
    previous = os.environ.get("POSTGRES_DB")
    os.environ["POSTGRES_DB"] = name
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("POSTGRES_DB", None)
        else:
            os.environ["POSTGRES_DB"] = previous


def alembic_upgrade(url: str, revision: str = "head") -> None:
    """Migrates `url` up to `revision`."""
    with database_env(url):
        command.upgrade(Config(str(PROJECT_ROOT / "alembic.ini")), revision)


def alembic_downgrade(url: str, revision: str) -> None:
    """Migrates `url` back down to `revision`."""
    with database_env(url):
        command.downgrade(Config(str(PROJECT_ROOT / "alembic.ini")), revision)


@pytest.fixture
def empty_database() -> Iterator[str]:
    """A freshly created, entirely empty database. Dropped when the test ends."""
    server = _server_url()
    name = f"calltrainer_test_{uuid.uuid4().hex[:12]}"
    admin = create_engine(server.set(database="postgres"), isolation_level="AUTOCOMMIT")

    try:
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{name}"'))
    except OperationalError as e:
        admin.dispose()
        pytest.skip(f"No reachable PostgreSQL server for the tests: {e}")

    try:
        yield _render(server.set(database=name))
    finally:
        with admin.connect() as conn:
            # FORCE terminates leftover connections; without it a session the
            # test failed to close would block the drop and leak the database.
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture
def migrated_database(empty_database: str) -> str:
    """An empty database with all migrations applied."""
    alembic_upgrade(empty_database)
    return empty_database


@pytest.fixture
def db_session(migrated_database: str) -> Iterator[DbSession]:
    """An ORM session against a migrated, empty database."""
    engine = create_engine(migrated_database)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


PERSONA_KEY = "thomas-brandt-ceo"
SCENARIO_KEY = "price-cancellation-risk"
METRIC_KEY = "speaking_rate"

SESSION_STARTED = datetime(2026, 8, 27, 10, 0, 0, tzinfo=UTC)
SESSION_ENDED = datetime(2026, 8, 27, 10, 4, 0, tzinfo=UTC)


def make_finished_session(
    *,
    extern_id: uuid.UUID | None = None,
    reason: str = "user",
    turns: list[Turn] | None = None,
    persona_key: str = PERSONA_KEY,
) -> FinishedSession:
    """A ready-to-save Session pointing at the `reference_data` rows.

    Shared by the write and read tests so they agree on what a stored Session
    looks like; each overrides only the part it is actually about.
    """
    return FinishedSession(
        extern_id=extern_id or uuid.uuid4(),
        subject_id=str(uuid.uuid4()),
        persona_key=persona_key,
        scenario_key=SCENARIO_KEY,
        language_code="de",
        reason=reason,
        started_at=SESSION_STARTED,
        ended_at=SESSION_ENDED,
        turns=turns if turns is not None else [],
    )


@dataclass
class ReferenceRows:
    """The reference entities a Session has to point at, as created by
    `reference_data`. Shared so the Session-related tests describe the same
    starting world instead of each building their own."""

    persona: Persona
    scenario: Scenario
    language: Language
    metric_type: MetricType


@pytest.fixture
def reference_data(db_session: DbSession) -> ReferenceRows:
    """Seeds the minimum reference data a Session needs, by hand rather than
    through the seed script, so these tests do not depend on what personas.py
    happens to contain."""
    language = Language(code="de", name="Deutsch")
    persona = Persona(
        key=PERSONA_KEY,
        name="Thomas Brandt",
        role="Geschäftsführer",
        traits="sachlich",
        behavior="Verhalten",
        training_goal="",
        difficulty="mittel",
        language_code="de",
        tts_voice="de_male",
        active=True,
    )
    scenario = Scenario(
        key=SCENARIO_KEY,
        scenario_type="Preisgespräch",
        title="Kündigungsabsicht",
        description="Beschreibung",
        active=True,
    )
    metric_type = MetricType(
        key=METRIC_KEY, name="Sprechtempo", unit="Wörter/min", active=True
    )
    db_session.add_all([language, persona, scenario, metric_type])
    db_session.commit()
    return ReferenceRows(
        persona=persona, scenario=scenario, language=language, metric_type=metric_type
    )


@pytest.fixture
async def api_client(migrated_database: str) -> AsyncIterator[httpx.AsyncClient]:
    """The FastAPI app, wired to this test's throwaway database.

    Driven through httpx's ASGI transport rather than Starlette's TestClient:
    the pinned starlette (0.35) passes `app=` to httpx.Client, which httpx 0.28
    no longer accepts. Going through the transport exercises the same ASGI
    stack without touching either pin.

    The application memoises its engine, so the settings override alone would
    not reach it — reset_engine() is what makes it pick up the test database,
    and again afterwards so the next test is unaffected.
    """
    with database_env(migrated_database):
        reset_engine()
        # Imported here, not at module scope: importing the app is what builds
        # the routes, and it must happen with the test settings in place.
        from backend.app import app  # pylint: disable=import-outside-toplevel

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client
    reset_engine()
