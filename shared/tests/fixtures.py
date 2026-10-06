"""Fixtures every suite shares: the environment, set before any package import, and
a throwaway database per persistence test (skipped without a server)."""

# The environment must be set before any package import.
# pylint: disable=wrong-import-position,missing-function-docstring

import os

os.environ.setdefault("DIREKT_URL", "http://direkt.test.invalid")
os.environ.setdefault("DIREKT_API_KEY", "test-direkt-key")
os.environ.setdefault("LLM_MODEL", "test-llm-model")
os.environ.setdefault("LOG_FORMAT", "pretty")

# The developer's own server, taken before the guard below replaces it.
_SERVER = os.environ.get("POSTGRES_URL")
_SERVER_PASSWORD = os.environ.get("POSTGRES_PASSWORD")

# Unusable on purpose, so a stray session_scope() or enqueue fails loudly.
# Assigned, not setdefault: the sourced .env has already set the real ones.
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


PROJECT_ROOT = Path(__file__).resolve().parents[2]

_DB_CONNECT_TIMEOUT = 3


def _loopback(host: str | None) -> str | None:
    """`localhost` -> `127.0.0.1`: on Windows it resolves to `::1` first, which
    Docker Desktop does not forward, and Alembic's connect then hangs."""
    return "127.0.0.1" if host in ("localhost", "::1") else host


def _render(url: URL) -> str:
    # str(URL) masks the password.
    return url.render_as_string(hide_password=False)


def _server_url() -> URL:
    """The configured database server, or a skip if none was sourced."""
    if not _SERVER:
        return pytest.skip("POSTGRES_URL is not set; `source .env` to run the persistence tests")
    url = make_url(_SERVER).set(drivername=DRIVER)
    if _SERVER_PASSWORD:
        url = url.set(password=_SERVER_PASSWORD)
    return url.set(host=_loopback(url.host))


@contextmanager
def database_env(url: str) -> Iterator[None]:
    """Aims Alembic and `build_database_url()` at `url` for the block."""
    previous = os.environ["POSTGRES_URL"]
    os.environ["POSTGRES_URL"] = url
    try:
        yield
    finally:
        os.environ["POSTGRES_URL"] = previous


def _alembic_config() -> Config:
    # Otherwise env.py's fileConfig() disables existing loggers for the session.
    config = Config(str(ALEMBIC_INI))
    config.attributes["configure_logging"] = False
    return config


def alembic_upgrade(url: str, revision: str = "head") -> None:
    with database_env(url):
        command.upgrade(_alembic_config(), revision)


def alembic_downgrade(url: str, revision: str) -> None:
    with database_env(url):
        command.downgrade(_alembic_config(), revision)


@pytest.fixture(scope="session")
def _reachable_postgres() -> URL:
    """Probed once, so an offline server skips everything in one shot."""
    server = _server_url()
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
    server = _reachable_postgres
    name = f"calltrainer_test_{uuid.uuid4().hex[:12]}"
    admin = create_engine(server.set(database="postgres"), isolation_level="AUTOCOMMIT")

    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))

    try:
        yield _render(server.set(database=name))
    finally:
        with admin.connect() as conn:
            # FORCE: a connection the test left open would block the drop.
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture
def migrated_database(empty_database: str) -> str:
    alembic_upgrade(empty_database)
    return empty_database


@pytest.fixture
def db_session(migrated_database: str) -> Iterator[DbSession]:
    engine = create_engine(migrated_database)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def app_database(migrated_database: str) -> Iterator[str]:
    """Points the application's memoised engine at this test's database."""
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
    persona: db_models.Persona
    scenario: db_models.Scenario
    language: db_models.Language
    metric_type: db_models.MetricType


@pytest.fixture
def reference_data(db_session: DbSession) -> ReferenceRows:
    """Built by hand, independent of the seed content."""
    language = db_models.Language(code="de", name="Deutsch")
    default_tenant = db_models.Tenant(extern_ref="default", name="Ohne Unternehmen")
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
    # From the real seed: the wrap-up resolves tags against these keys.
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
    """Replace `llm.complete`; returns one `(messages, think)` pair per call."""
    calls: list[tuple[list[dict[str, str]], bool]] = []

    # pylint: disable=unused-argument  # mirrors llm.complete's signature
    async def complete(messages: list[dict[str, str]], *,
                       max_tokens: int | None = None, think: bool = False) -> str:
        calls.append((messages, think))
        return reply(messages) if callable(reply) else reply

    monkeypatch.setattr(llm, "complete", complete)
    return calls


def asked(calls, index: int = 0) -> str:
    """Everything the model was told on one call."""
    return "\n".join(message["content"] for message in calls[index][0])
