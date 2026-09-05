"""Shared test fixtures.

Two suites share this file. Most tests fake the STT/LLM/TTS pipeline and never
touch a database; the persistence tests get a real one, created fresh per test
and dropped afterwards, so a failing test can never leave the development
database half-migrated and tests cannot see each other's rows.

That split is why the POSTGRES_* settings are claimed with deliberately
unusable values below, before the backend is imported: a test that does not ask
for a database must not be able to reach the real one by accident. The
persistence fixtures read .env separately (`_ENV`, via dotenv_values, which
leaves os.environ alone) and inject only their own throwaway database, for the
duration of the test. Without those settings in .env, or without a reachable
server, they skip rather than fail, so a checkout without Postgres still gets a
green run of everything else.

The backend reads a handful of environment variables at import time
(`backend/clients/config.py`), so they are set here *before* any backend
module is imported. Values are dummies: no test in this suite makes a real
network call — every pipeline backend (STT / LLM / TTS) is faked.

`DEBUG=true` keeps TTS config fully offline (no KugelAudio client is
constructed); the KugelAudio-default / DiReKT-fallback dispatch is still
covered in `test_tts_fallback.py` by patching the tts module directly.
"""

# The env vars below must be set before backend imports run, so those imports
# deliberately sit after this block.
# pylint: disable=wrong-import-position,missing-function-docstring
# pylint: disable=too-few-public-methods,redefined-outer-name

import os

os.environ.setdefault("DIREKT_URL", "http://direkt.test.invalid")
os.environ.setdefault("DIREKT_API_KEY", "test-direkt-key")
os.environ.setdefault("STT_MODEL", "test-stt-model")
os.environ.setdefault("LLM_MODEL", "test-llm-model")
os.environ.setdefault("TTS_MODEL", "test-tts-model")
os.environ.setdefault("KUGELAUDIO_MODEL", "test-kugelaudio-model")
os.environ.setdefault("KUGELAUDIO_API_KEY", "test-kugelaudio-key")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("OIDC_ISSUER", "http://keycloak.test.invalid/realms/direkt")

# Deliberately unusable credentials, and the reason they are set here at all:
# backend/clients/config.py calls load_dotenv() when the backend is first
# imported, which would otherwise put the developer's real POSTGRES_* into the
# environment for the whole test session. python-dotenv does not override
# variables that are already set, so claiming them first is what keeps a stray
# session_scope() out of the development database — it fails to connect instead
# of quietly writing to it. The database fixtures below override all three for
# the duration of a test that actually asks for one.
os.environ.setdefault("POSTGRES_USER", "calltrainer-test-no-such-user")
os.environ.setdefault("POSTGRES_PASSWORD", "not-a-real-password")
os.environ.setdefault("POSTGRES_DB", "calltrainer-test-no-such-database")

import uuid  # noqa: E402
from collections.abc import AsyncIterator, Iterator  # noqa: E402
from contextlib import contextmanager  # noqa: E402
from dataclasses import dataclass, replace  # noqa: E402
from datetime import UTC, datetime  # noqa: E402
from pathlib import Path  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from dotenv import dotenv_values  # noqa: E402
from kugelaudio.exceptions import KugelAudioError  # noqa: E402
from openai import OpenAIError  # noqa: E402
from sqlalchemy import URL, create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402
from sqlalchemy.orm import Session as DbSession  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from backend import auth, library  # noqa: E402
from backend.app import app  # noqa: E402
from backend.clients import llm, stt, tts  # noqa: E402
from backend.personas import Persona, PersonaVoice  # noqa: E402
from backend.scenarios import Scenario  # noqa: E402
# The ORM models keep a namespace: `Persona` and `Scenario` above are the value
# objects the app passes around, and both names would otherwise collide here.
from backend.db import models as db_models  # noqa: E402
from backend.db.session import reset_engine, session_scope  # noqa: E402
from backend.session.models import AudioChunk, Failed, StateChanged, TurnCompleted  # noqa: E402
from backend.session.models import Turn  # noqa: E402

# Personas and Scenarios live in the database since ADR 0041, so the suite can
# no longer import a hardcoded library -- and must not need a database to run.
# These are test doubles: value objects of the same shape, owned by the suite.
# Whether the *seeded* content is any good is a separate question, checked in
# test_persona_scenario_library.py against the seed script.
TEST_PERSONAS = [
    Persona(
        id="test-persona-de",
        name="Thomas Brandt",
        language_id="de",
        language_name="Deutsch",
        voice=PersonaVoice(tts_voice="de_male", kugelaudio_voice_id=1885),
        role_label="Geschäftsführer, Fokus auf Strategie & Budget",
        role="Managing director of a mid-sized company, focused on strategy and budget",
        traits="matter-of-fact, time-conscious, an experienced negotiator",
        behavior="You press for concrete answers and never settle for a vague one.",
    ),
    Persona(
        id="test-persona-en",
        name="Samantha Ferris",
        language_id="en",
        language_name="Englisch",
        voice=PersonaVoice(tts_voice="de_female", kugelaudio_voice_id=1071),
        role_label="Marketing-Managerin bei einem Kundenunternehmen",
        role="Marketing manager at a company that is a customer of the user's",
        traits="very polite, calm and composed, never pushy",
        behavior="You stay friendly throughout, but keep asking until an answer is concrete.",
    ),
]

TEST_SCENARIOS = [
    Scenario(
        id="test-scenario-support",
        name="Offenes Anliegen zu bestehendem Vertrag",
        short_description="Der Kunde ruft mit einer offenen Frage zu einem bestehenden Vertrag an.",
        description=(
            "The customer (the persona) is calling the user, who works in support, "
            "about an unresolved issue with an existing contract."
        ),
    ),
    Scenario(
        id="test-scenario-price",
        name="Kündigungsabsicht wegen Preis",
        short_description="Der Kunde erwägt zu kündigen, weil ihm die Kosten zu hoch sind.",
        description=(
            "The customer (the persona) is calling to say they are considering "
            "cancelling, because the running costs seem too high for the benefit."
        ),
    ),
]


REPO = Path(__file__).resolve().parent.parent


def load_seed_module():
    """The library's initial content (ADR 0041).

    It moved from `scripts/seed_reference_data.py` into `backend/db/seed_data.py`
    when provisioning became part of application startup, so this is a plain
    import now -- kept as a function so the tests that check *what* the library
    ships still have one place to get it from.
    """
    from backend.db import seed_data

    return seed_data


# A fixed caller for tests that don't care about auth (most of them).
TEST_AUTH = auth.AuthContext(sub="test-subject", roles=[], token="test-token")


@pytest.fixture
def auth_ctx():
    return TEST_AUTH


@pytest.fixture(autouse=True)
def _override_auth():
    """Every test runs as `TEST_AUTH` unless it clears the override itself
    (see `test_setup_api.py`'s unauthenticated cases)."""
    app.dependency_overrides[auth.require_user] = lambda: TEST_AUTH
    yield
    app.dependency_overrides.pop(auth.require_user, None)


@pytest.fixture
def persona():
    return TEST_PERSONAS[0]


@pytest.fixture
def scenario():
    return TEST_SCENARIOS[0]


@pytest.fixture
def fake_library(monkeypatch):
    """Serve the test doubles in place of the database-backed library.

    ADR 0041 put the database on the Session's start path, so anything that
    goes through `/api/personas` or the `/ws/session` handshake would otherwise
    need one. Patched on the `library` module itself, which is how both call
    sites look the functions up."""
    by_id = {p.id: p for p in TEST_PERSONAS}
    by_key = {s.id: s for s in TEST_SCENARIOS}
    # Personas are curated (no scoping); a Scenario read is scoped to the
    # caller's `sub` + tenant (ADR 0058/0060), which the doubles ignore -- the real
    # visibility query is tested against a database in test_authored_content.py.
    # The WS handshake's tenant resolution is stubbed so it needs no database.
    monkeypatch.setattr(library, "list_personas", lambda: list(TEST_PERSONAS))
    monkeypatch.setattr(library, "list_scenarios", lambda subject, tenant_id=1: list(TEST_SCENARIOS))
    monkeypatch.setattr(library, "get_persona", lambda extern_id: by_id.get(extern_id))
    monkeypatch.setattr(library, "get_scenario", lambda extern_id, subject=None, tenant_id=1: by_key.get(extern_id))
    monkeypatch.setattr("backend.api.session_ws.resolve_tenant_id", lambda auth: 1)
    return library


class FakeLLM:
    """Stand-in for `backend.clients.llm.stream_reply`.

    Configure `.replies` with the successive full replies to stream (one per
    call). Each reply is emitted as several token deltas so the chunker and
    the streaming pipeline see realistic input. Set `.fail_times` to raise an
    OpenAIError on the first N calls before serving a reply.
    """

    def __init__(self, replies=None):
        self.replies = list(replies or ["Alles klar, danke."])
        self.calls = []
        self.fail_times = 0

    def stream_reply(self, messages):
        self.calls.append(messages)

        async def _gen():
            if self.fail_times > 0:
                self.fail_times -= 1
                raise OpenAIError("simulated LLM failure")
            reply = self.replies.pop(0) if self.replies else ""
            for i, word in enumerate(reply.split(" ")):  # mimic token streaming
                yield word if i == 0 else " " + word

        return _gen()


class FakeSTT:
    """Stand-in for `backend.clients.stt.transcribe`."""

    def __init__(self, transcripts=None):
        self.transcripts = list(transcripts or ["Hallo, worum geht es?"])
        self.calls = []
        self.fail_times = 0

    async def transcribe(self, audio_bytes, filename, content_type, language_id):
        self.calls.append((audio_bytes, filename, content_type, language_id))
        if self.fail_times > 0:
            self.fail_times -= 1
            raise OpenAIError("simulated STT failure")
        return self.transcripts.pop(0) if self.transcripts else ""


class FakeTTS:
    """Stand-in for `backend.clients.tts.synthesize_stream` (+ one-shot
    `synthesize`).

    `synthesize_stream` mimics the real KugelAudio->DiReKT fallback as a
    two-attempt sequence: a `fail_times` of 1 is "KugelAudio blipped, DiReKT
    covered it" (absorbed, 2 recorded calls); a higher count exhausts both and
    raises (-> `tts_failed`). Set `.hang` to an `asyncio.Event` to park
    synthesis (barge-in tests). `.chunks_per_call` controls how many audio
    sub-chunks one text chunk yields.
    """

    def __init__(self):
        self.calls = []
        self.fail_times = 0
        self.hang = None
        self.chunks_per_call = 1

    async def synthesize_stream(self, text, voice, language_id):
        for _ in range(2):  # KugelAudio attempt, then the DiReKT fallback
            self.calls.append((text, voice, language_id))
            if self.hang is not None:
                await self.hang.wait()
            if self.fail_times > 0:
                self.fail_times -= 1
                continue
            for _ in range(self.chunks_per_call):
                yield b"AUDIO:" + text.encode("utf-8")
            return
        raise KugelAudioError("simulated TTS failure")

    async def synthesize(self, text, voice, language_id):
        self.calls.append((text, voice, language_id))
        if self.hang is not None:
            await self.hang.wait()
        if self.fail_times > 0:
            self.fail_times -= 1
            raise KugelAudioError("simulated TTS failure")
        return b"AUDIO:" + text.encode("utf-8")


@pytest.fixture
def fake_pipeline(monkeypatch):
    """Patch STT, LLM and TTS on the modules the orchestrator calls them
    through. Returns the three fakes so a test can inspect/seed them."""
    llm_fake = FakeLLM()
    stt_fake = FakeSTT()
    tts_fake = FakeTTS()

    monkeypatch.setattr(llm, "stream_reply", llm_fake.stream_reply)
    monkeypatch.setattr(stt, "transcribe", stt_fake.transcribe)
    monkeypatch.setattr(tts, "synthesize_stream", tts_fake.synthesize_stream)
    monkeypatch.setattr(tts, "synthesize", tts_fake.synthesize)

    class Pipeline:
        """Bundle of the three fakes active for one test."""

        llm = llm_fake
        stt = stt_fake
        tts = tts_fake

    return Pipeline()


async def collect(turn_events):
    """Drain an async iterator of TurnEvents into a list."""
    return [event async for event in turn_events]


def states(events):
    """The ordered `StateChanged` values in an event list."""
    return [e.state for e in events if isinstance(e, StateChanged)]


def audio_chunks(events):
    """The `AudioChunk` events in an event list."""
    return [e for e in events if isinstance(e, AudioChunk)]


def completed(events):
    """The first `TurnCompleted` event, or None."""
    return next((e for e in events if isinstance(e, TurnCompleted)), None)


def failure(events):
    """The first `Failed` event, or None."""
    return next((e for e in events if isinstance(e, Failed)), None)


# --- Database fixtures ----------------------------------------------------
# Everything below is for the persistence tests. A test that does not request
# one of these fixtures never opens a connection to Postgres at all.

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Read, not loaded: dotenv_values leaves os.environ alone, so a test that does
# not request a database fixture still has no POSTGRES_* set and cannot connect.
_ENV = dotenv_values(PROJECT_ROOT / ".env")

# The POSTGRES_* keys database_env() injects; host and port fall back to the
# same defaults backend/db/session.py applies.
_DB_SETTINGS = ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB",
                "POSTGRES_HOST", "POSTGRES_PORT")

# Bounds the reachability probe so an unreachable server fails in a few seconds
# instead of hanging on libpq's default. psycopg tries both the IPv6 and the
# IPv4 address, so the wait is up to twice this.
_DB_CONNECT_TIMEOUT = 3


def _render(url: URL) -> str:
    """URL.__str__ masks the password, which makes the result unusable as a
    connection string — this keeps it."""
    return url.render_as_string(hide_password=False)


def _server_url() -> URL:
    """The configured database server, or a skip if .env is incomplete."""
    missing = [k for k in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB")
               if not _ENV.get(k)]
    if missing:
        # `return` only so every path returns an expression: skip() raises.
        return pytest.skip(f"Database settings missing from .env: {', '.join(missing)}")
    return URL.create(
        "postgresql+psycopg",
        username=_ENV["POSTGRES_USER"],
        password=_ENV["POSTGRES_PASSWORD"],
        host=_ENV.get("POSTGRES_HOST") or "localhost",
        port=int(_ENV.get("POSTGRES_PORT") or 5432),
        database=_ENV["POSTGRES_DB"],
    )


@contextmanager
def database_env(url: str) -> Iterator[None]:
    """Puts the POSTGRES_* settings for `url` into the environment for the block.

    Alembic's env.py and backend/db/session.py both call `build_database_url()`,
    which assembles the connection from POSTGRES_*, so setting those is how a
    test aims them at its own throwaway database. Restored afterwards, down to
    "was not set before", so the next test starts unable to connect again.
    """
    parsed = make_url(url)
    values = {
        "POSTGRES_USER": parsed.username,
        "POSTGRES_PASSWORD": parsed.password,
        "POSTGRES_DB": parsed.database,
        "POSTGRES_HOST": parsed.host,
        "POSTGRES_PORT": str(parsed.port or 5432),
    }
    previous = {k: os.environ.get(k) for k in _DB_SETTINGS}
    os.environ.update(values)
    try:
        yield
    finally:
        for key, was in previous.items():
            if was is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = was


def alembic_upgrade(url: str, revision: str = "head") -> None:
    """Migrates `url` up to `revision`."""
    with database_env(url):
        command.upgrade(Config(str(PROJECT_ROOT / "alembic.ini")), revision)


def alembic_downgrade(url: str, revision: str) -> None:
    """Migrates `url` back down to `revision`."""
    with database_env(url):
        command.downgrade(Config(str(PROJECT_ROOT / "alembic.ini")), revision)


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

    backend/db/session.py memoises its engine, so the settings override alone
    would not reach it — reset_engine() is what makes it pick the test database
    up, and again afterwards so the next test is unaffected. Needed by anything
    that goes through session_scope() rather than taking a session as an
    argument, which is every write path since ADR 0034.
    """
    with database_env(migrated_database):
        reset_engine()
        yield migrated_database
    reset_engine()


@pytest.fixture
def seeded_database(app_database: str) -> str:
    """`app_database`, with the reference tables filled from seed_data.py /
    metrics.py — the state the application boots into.

    For the setup endpoints, which read the persona and scenario tables
    (ADR 0041) and therefore have nothing to serve without this.
    """
    # Imported here so a collection-time import never needs the environment.
    from backend.db.provision import seed  # pylint: disable=import-outside-toplevel

    with session_scope() as db:
        seed(db)
    return app_database


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
    # Built-ins: public and authored by nobody (ADR 0058), like a seeded row.
    persona = db_models.Persona(
        key=PERSONA_KEY,
        name="Thomas Brandt",
        role_label="Geschäftsführer, Strategie & Budget",
        role="Geschäftsführer",
        traits="sachlich",
        behavior="Verhalten",
        training_goal="",
        difficulty="mittel",
        language_code="de",
        tts_voice="de_male",
        active=True,
        visibility=db_models.VISIBILITY_PUBLIC,
    )
    scenario = db_models.Scenario(
        key=SCENARIO_KEY,
        scenario_type="Preisgespräch",
        title="Kündigungsabsicht",
        short_description="Kunde erwägt zu kündigen.",
        description="Beschreibung",
        case_facts="",
        call_goal="",
        success_condition="",
        active=True,
        visibility=db_models.VISIBILITY_PUBLIC,
    )
    metric_type = db_models.MetricType(
        key=METRIC_KEY, name="Sprechtempo", unit="Wörter/min", feature_id="F-36", active=True
    )
    db_session.add_all([language, default_tenant, persona, scenario, metric_type])
    db_session.commit()
    return ReferenceRows(
        persona=persona, scenario=scenario, language=language, metric_type=metric_type
    )


def persist(
    *,
    extern_id: uuid.UUID | None = None,
    reason: str = "user",
    turns: list[Turn] | None = None,
    persona_key: str = PERSONA_KEY,
) -> uuid.UUID:
    """Write a Session through the real write path; returns its extern_id.

    persist_session() opens its own session_scope(), so this needs the
    `app_database` fixture rather than `db_session` — the two see the same
    database, but only the former is what the application itself connects to.
    """
    # Imported here, not at module scope: importing the write path pulls in
    # the feedback stack, which a collection-time import should not need.
    from backend.session import persistence  # pylint: disable=import-outside-toplevel

    # The value object the write path receives carries the row's `extern_id` as
    # `.id` since ADR 0058, so resolve it from the reference row the fixture
    # inserted. A `persona_key` the fixture did not write yields a random id,
    # which exercises the LookupError path.
    with session_scope() as db:
        prow = db.query(db_models.Persona).filter_by(key=persona_key).one_or_none()
        srow = db.query(db_models.Scenario).filter_by(key=SCENARIO_KEY).one_or_none()
    persona = replace(TEST_PERSONAS[0], id=str(prow.extern_id) if prow else str(uuid.uuid4()))
    scenario = replace(TEST_SCENARIOS[0], id=str(srow.extern_id) if srow else str(uuid.uuid4()))
    extern_id = extern_id or uuid.uuid4()
    persistence.persist_session(
        extern_id,
        str(uuid.uuid4()),
        persona,
        scenario,
        turns if turns is not None else [],
        SESSION_STARTED,
        reason,
    )
    return extern_id


@pytest.fixture
async def api_client(app_database: str) -> AsyncIterator[httpx.AsyncClient]:  # pylint: disable=unused-argument
    """The FastAPI app, wired to this test's throwaway database.

    `app_database` is requested for its effect, not its value: it is what points
    the application's engine at this test's database.

    Driven through httpx's ASGI transport rather than Starlette's TestClient:
    the pinned starlette (0.35) passes `app=` to httpx.Client, which httpx 0.28
    no longer accepts. Going through the transport exercises the same ASGI
    stack without touching either pin.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
