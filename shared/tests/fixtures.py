"""The fixtures every suite shares, registered by each suite's conftest.py:
the environment the packages read at import, and the throwaway databases the
persistence tests run against.

Most tests fake the pipeline and never touch a database; the persistence tests
get a throwaway database per test, on the server `POSTGRES_URL` names in the
environment the suite was started from (`source .env && uv run pytest`), and
skip without one. The packages read their environment at import time, so it is
set up below before any import."""

# The env vars below must be set before any package import runs, so those imports
# deliberately sit after this block.
# pylint: disable=wrong-import-position,missing-function-docstring

import os

os.environ.setdefault("DIREKT_URL", "http://direkt.test.invalid")
os.environ.setdefault("DIREKT_API_KEY", "test-direkt-key")
os.environ.setdefault("LLM_MODEL", "test-llm-model")
os.environ.setdefault("LOG_FORMAT", "pretty")

# The server the persistence tests create their databases on: the developer's
# own, as sourced from .env. Taken before the guard below replaces it.
_SERVER = os.environ.get("POSTGRES_URL")
_SERVER_PASSWORD = os.environ.get("POSTGRES_PASSWORD")

# Deliberately unusable settings, so a stray session_scope() or enqueue fails
# loudly instead of writing to the development database or queue. Assigned, not
# setdefault: the sourced .env has already set the real ones, and setdefault
# would leave the guard off exactly there. The database fixtures aim the app at
# a throwaway database per test (`database_env`).
os.environ["POSTGRES_URL"] = "postgresql://calltrainer-test-no-such-user@127.0.0.1:1/no-such-database"
os.environ["REDIS_URL"] = "redis://127.0.0.1:1"
for _name in ("POSTGRES_URL_FILE", "POSTGRES_PASSWORD", "POSTGRES_PASSWORD_FILE", "REDIS_URL_FILE"):
    os.environ.pop(_name, None)

import uuid  # noqa: E402
from collections.abc import Iterator  # noqa: E402
from contextlib import contextmanager  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from datetime import UTC, datetime  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import URL, create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402
from sqlalchemy.orm import Session as DbSession  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from shared.clients import llm  # noqa: E402
from shared.db import ALEMBIC_INI, models as db_models  # noqa: E402
from shared.db.seed_data import FOCUS_GOALS  # noqa: E402
from shared.db.session import DRIVER, reset_engine  # noqa: E402


# --- Database fixtures ----------------------------------------------------
# Everything below is for the persistence tests. A test that does not request
# one of these fixtures never opens a connection to Postgres at all.

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Bounds the reachability probe so an unreachable server fails in a few seconds
# instead of hanging on libpq's default.
_DB_CONNECT_TIMEOUT = 3


def _loopback(host: str | None) -> str | None:
    """`localhost` -> `127.0.0.1` for the test database server.

    On Windows `localhost` resolves to `::1` first, but Docker Desktop forwards IPv4
    only, so every connect waits out a timeout (Alembic's has none) and the run hangs.
    """
    return "127.0.0.1" if host in ("localhost", "::1") else host


def _render(url: URL) -> str:
    """URL.__str__ masks the password, which makes the result unusable as a
    connection string — this keeps it."""
    return url.render_as_string(hide_password=False)


def _server_url() -> URL:
    """The configured database server, or a skip if none was sourced."""
    if not _SERVER:
        # `return` only so every path returns an expression: skip() raises.
        return pytest.skip("POSTGRES_URL is not set; `source .env` to run the persistence tests")
    url = make_url(_SERVER).set(drivername=DRIVER)
    if _SERVER_PASSWORD:
        url = url.set(password=_SERVER_PASSWORD)
    return url.set(host=_loopback(url.host))


@contextmanager
def database_env(url: str) -> Iterator[None]:
    """Points `POSTGRES_URL` at `url` for the block.

    That is how Alembic and `build_database_url()` are aimed at a test's database.
    Restored afterwards, so the next test is back on the unusable placeholder.
    """
    previous = os.environ["POSTGRES_URL"]
    os.environ["POSTGRES_URL"] = url
    try:
        yield
    finally:
        os.environ["POSTGRES_URL"] = previous


def _alembic_config() -> Config:
    """Alembic settings for a programmatic migration inside the test process.

    `configure_logging=False`: env.py's fileConfig() otherwise disables every existing
    logger for the rest of the session, breaking later tests that assert on logs.
    """
    config = Config(str(ALEMBIC_INI))
    config.attributes["configure_logging"] = False
    return config


def alembic_upgrade(url: str, revision: str = "head") -> None:
    """Migrates `url` up to `revision`."""
    with database_env(url):
        command.upgrade(_alembic_config(), revision)


def alembic_downgrade(url: str, revision: str) -> None:
    """Migrates `url` back down to `revision`."""
    with database_env(url):
        command.downgrade(_alembic_config(), revision)


@pytest.fixture(scope="session")
def _reachable_postgres() -> URL:
    """The configured server, probed once. If it is down, every persistence
    test skips here in one shot -- without this each fixture re-times-out its
    own connection, which turned an offline `pytest` into a multi-minute wait.
    """
    server = _server_url()  # skips if .env is incomplete
    probe = create_engine(
        server.set(database="postgres"),
        connect_args={"connect_timeout": _DB_CONNECT_TIMEOUT},
    )
    try:
        with probe.connect():
            pass
    except OperationalError as e:
        pytest.skip(f"No reachable PostgreSQL server for the tests: {e}")
    finally:
        probe.dispose()
    return server


@pytest.fixture
def empty_database(_reachable_postgres: URL) -> Iterator[str]:
    """A freshly created, entirely empty database. Dropped when the test ends."""
    server = _reachable_postgres
    name = f"calltrainer_test_{uuid.uuid4().hex[:12]}"
    admin = create_engine(server.set(database="postgres"), isolation_level="AUTOCOMMIT")

    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))

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


@pytest.fixture
def app_database(migrated_database: str) -> Iterator[str]:
    """Points the *application's* engine at this test's throwaway database.

    session.py memoises its engine, so reset_engine() is needed before and after.
    Required by anything going through session_scope() (every write path, ADR 0034).
    """
    with database_env(migrated_database):
        reset_engine()
        yield migrated_database
    reset_engine()


PERSONA_KEY = "thomas-brandt-ceo"
SCENARIO_KEY = "price-cancellation-risk"
METRIC_KEY = "pace"

SESSION_STARTED = datetime(2026, 8, 27, 10, 0, 0, tzinfo=UTC)


@dataclass
class ReferenceRows:
    """The reference entities a Session has to point at, as created by
    `reference_data`. Shared so the Session-related tests describe the same
    starting world instead of each building their own."""

    persona: db_models.Persona
    scenario: db_models.Scenario
    language: db_models.Language
    metric_type: db_models.MetricType


@pytest.fixture
def reference_data(db_session: DbSession) -> ReferenceRows:
    """Seeds the minimum reference data a Session needs, by hand rather than
    through the seed script, so these tests do not depend on what personas.py
    happens to contain."""
    language = db_models.Language(code="de", name="Deutsch")
    # The default tenant every caller with no company resolves to (ADR 0060).
    default_tenant = db_models.Tenant(extern_ref="default", name="Ohne Unternehmen")
    # Built-ins: the Scenario public and authored by nobody (ADR 0058), like a seeded row.
    persona = db_models.Persona(
        key=PERSONA_KEY,
        name="Thomas Brandt",
        role_label="Geschäftsführer, Strategie & Budget",
        role="Geschäftsführer",
        traits="sachlich",
        behavior="Verhalten",
        training_goal="",
        language_code="de",
        active=True,
    )
    scenario = db_models.Scenario(
        key=SCENARIO_KEY,
        title="Kündigungsabsicht",
        short_description="Kunde erwägt zu kündigen.",
        description="Beschreibung",
        case_facts="",
        call_goal="",
        active=True,
        visibility=db_models.VISIBILITY_PUBLIC,
    )
    metric_type = db_models.MetricType(
        key=METRIC_KEY, name="Sprechtempo", unit="Wörter/min", aspect=db_models.ASPECT_HOW,
        feature_id="F-36", active=True,
    )
    # The focus catalogue, from the same list that seeds it in production. Not
    # hand-written like the rows above: the wrap-up resolves each point's tag
    # against these keys (`generator._goal_ids`), so a made-up catalogue here
    # would let a test pass on a key the real system does not have.
    focus_goals = [
        db_models.FocusGoal(
            key=goal["id"], group_key=goal["group"], position=goal["position"],
            title=goal["title"], caption=goal["caption"], info=goal["info"],
            evidence=goal["evidence"], active=True,
        )
        for goal in FOCUS_GOALS
    ]
    db_session.add_all(
        [language, default_tenant, persona, scenario, metric_type, *focus_goals]
    )
    db_session.commit()
    return ReferenceRows(
        persona=persona, scenario=scenario, language=language, metric_type=metric_type
    )


def stub_completions(monkeypatch, reply) -> list[tuple[list[dict[str, str]], bool]]:
    """Replace `llm.complete` and record what it was asked.

    `reply` is the answer text, or a callable given the messages. Returns one
    `(messages, think)` pair per call, so a test can check what the model was told.
    """
    calls: list[tuple[list[dict[str, str]], bool]] = []

    # pylint: disable=unused-argument  # the signature has to mirror
    # `llm.complete`, whose callers pass max_tokens; what it is set to is
    # not what these tests are about.
    async def complete(messages: list[dict[str, str]], *,
                       max_tokens: int | None = None, think: bool = False) -> str:
        calls.append((messages, think))
        return reply(messages) if callable(reply) else reply

    monkeypatch.setattr(llm, "complete", complete)
    return calls


def asked(calls, index: int = 0) -> str:
    """Everything the model was told on one call, system prompt and material
    together -- what a prompt assertion is made against."""
    return "\n".join(message["content"] for message in calls[index][0])
