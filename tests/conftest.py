"""Shared test fixtures.

Most tests fake STT/LLM/TTS and never touch a database; the persistence tests get
a throwaway database per test and skip without a reachable Postgres. The backend
reads its environment at import time, so it is set up below before any import."""

# The env vars below must be set before backend imports run, so those imports
# deliberately sit after this block.
# pylint: disable=wrong-import-position,missing-function-docstring
# pylint: disable=too-few-public-methods,redefined-outer-name

import os

os.environ.setdefault("DIREKT_URL", "http://direkt.test.invalid")
os.environ.setdefault("DIREKT_API_KEY", "test-direkt-key")
os.environ.setdefault("STT_MODEL", "test-stt-model")
os.environ.setdefault("LLM_MODEL", "test-llm-model")
os.environ.setdefault("KUGELAUDIO_MODEL", "test-kugelaudio-model")
os.environ.setdefault("KUGELAUDIO_API_KEY", "test-kugelaudio-key")
os.environ.setdefault("OIDC_ISSUER", "http://keycloak.test.invalid/realms/direkt")

# Deliberately unusable credentials: backend/clients/config.py calls load_dotenv()
# on import, which would otherwise put the real POSTGRES_* into the environment and
# let a stray session_scope() write to the development database.
# Assigned, not setdefault: inside the app container compose has already loaded
# .env, and setdefault would leave the guard off exactly there. The database
# fixtures read .env themselves (`_ENV`) and override these per test.
os.environ["POSTGRES_USER"] = "calltrainer-test-no-such-user"
os.environ["POSTGRES_PASSWORD"] = "not-a-real-password"
os.environ["POSTGRES_DB"] = "calltrainer-test-no-such-database"

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
from backend.db.seed_data import FOCUS_GOALS  # noqa: E402
from backend.db.session import DEFAULT_DATABASE, DEFAULT_USER, reset_engine, session_scope  # noqa: E402
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
        voice=PersonaVoice(kugelaudio_voice_id=1885),
        role_label="Geschäftsführer, Fokus auf Strategie & Budget",
        traits_label="Sachlich, auf die Zeit bedacht, verhandlungserfahren.",
        training_goal="Einwandbehandlung unter Zeitdruck und Verbindlichkeit.",
        role="Managing director of a mid-sized company, focused on strategy and budget",
        traits="matter-of-fact, time-conscious, an experienced negotiator",
        behavior="You press for concrete answers and never settle for a vague one.",
    ),
    Persona(
        id="test-persona-en",
        name="Samantha Ferris",
        language_id="en",
        language_name="Englisch",
        voice=PersonaVoice(kugelaudio_voice_id=1071),
        role_label="Marketing-Managerin bei einem Kundenunternehmen",
        traits_label="Sehr höflich, ruhig und gefasst, nie drängend.",
        training_goal="Bedarfsermittlung und Konkretheit.",
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
        category="operations",
    ),
    Scenario(
        id="test-scenario-price",
        name="Kündigungsabsicht wegen Preis",
        short_description="Der Kunde erwägt zu kündigen, weil ihm die Kosten zu hoch sind.",
        description=(
            "The customer (the persona) is calling to say they are considering "
            "cancelling, because the running costs seem too high for the benefit."
        ),
        category="pricing",
    ),
]


REPO = Path(__file__).resolve().parent.parent


def load_seed_module():
    """The library's initial content (ADR 0041), from `backend/db/seed_data.py`."""
    from backend.db import seed_data  # pylint: disable=import-outside-toplevel

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

    Patched on the `library` module, where both call sites look the functions up.
    """
    by_id = {p.id: p for p in TEST_PERSONAS}
    by_key = {s.id: s for s in TEST_SCENARIOS}
    # Personas are curated (no scoping); a Scenario read is scoped to the
    # caller's `sub` + tenant (ADR 0058/0060), which the doubles ignore -- the real
    # visibility query is tested against a database in test_authored_content.py.
    # The WS handshake's tenant resolution is stubbed so it needs no database.
    monkeypatch.setattr(library, "list_personas", lambda: list(TEST_PERSONAS))
    monkeypatch.setattr(library, "list_scenarios", lambda subject, tenant_id=1: list(TEST_SCENARIOS))
    monkeypatch.setattr(library, "get_persona", by_id.get)
    monkeypatch.setattr(library, "get_scenario", lambda extern_id, subject=None, tenant_id=1: by_key.get(extern_id))
    monkeypatch.setattr("backend.api.session_ws.resolve_tenant_id", lambda auth: 1)
    return library


class FakeLLM:
    """Stand-in for `backend.clients.llm.stream_reply`.

    `.replies` are the successive full replies, each streamed as several token
    deltas; `.fail_times` raises an OpenAIError on the first N calls.
    """

    def __init__(self, replies=None):
        self.replies = list(replies or ["Alles klar, danke."])
        self.calls = []
        self.fail_times = 0
        # `complete` is the call-state notes refresh (ADR 0071): one call per
        # completed exchange. Empty by default, so the notes stay off and the
        # message list the older tests index into is unchanged.
        self.states = []
        self.state_calls = []
        self.state_fail_times = 0

    async def complete(self, messages, **_kwargs):
        self.state_calls.append(messages)
        if self.state_fail_times > 0:
            self.state_fail_times -= 1
            raise OpenAIError("simulated notes failure")
        return self.states.pop(0) if self.states else ""

    # `**_kwargs` so this keeps the real signature: `retries` is passed by the
    # boot check (clients/health.py) and a fake that rejected it would fail
    # where the real function works.
    def stream_reply(self, messages, **_kwargs):
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
    """Stand-in for `backend.clients.tts.synthesize_stream` (+ one-shot `synthesize`).

    One attempt per chunk (ADR 0103): `fail_times` raises `KugelAudioError`. `.hang`
    (an `asyncio.Event`) parks synthesis; `.chunks_per_call` sets sub-chunks per chunk.
    """

    def __init__(self):
        self.calls = []
        self.fail_times = 0
        self.hang = None
        self.chunks_per_call = 1

    async def synthesize_stream(self, text, voice, language_id):
        self.calls.append((text, voice, language_id))
        if self.hang is not None:
            await self.hang.wait()
        if self.fail_times > 0:
            self.fail_times -= 1
            raise KugelAudioError("simulated TTS failure")
        for _ in range(self.chunks_per_call):
            yield b"AUDIO:" + text.encode("utf-8")

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
    monkeypatch.setattr(llm, "complete", llm_fake.complete)
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
# instead of hanging on libpq's default.
_DB_CONNECT_TIMEOUT = 3


def _loopback(host: str) -> str:
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
    """The configured database server, or a skip if .env is incomplete."""
    missing = [k for k in ("POSTGRES_PASSWORD",) if not _ENV.get(k)]
    if missing:
        # `return` only so every path returns an expression: skip() raises.
        return pytest.skip(f"Database settings missing from .env: {', '.join(missing)}")
    return URL.create(
        "postgresql+psycopg",
        username=_ENV.get("POSTGRES_USER") or DEFAULT_USER,
        password=_ENV["POSTGRES_PASSWORD"],
        host=_loopback(_ENV.get("POSTGRES_HOST") or "localhost"),
        port=int(_ENV.get("POSTGRES_PORT") or 5432),
        database=_ENV.get("POSTGRES_DB") or DEFAULT_DATABASE,
    )


@contextmanager
def database_env(url: str) -> Iterator[None]:
    """Puts the POSTGRES_* settings for `url` into the environment for the block.

    That is how Alembic and `build_database_url()` are aimed at a test's database.
    Restored afterwards, down to "was not set", so the next test cannot connect again.
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


def _alembic_config() -> Config:
    """Alembic settings for a programmatic migration inside the test process.

    `configure_logging=False`: env.py's fileConfig() otherwise disables every existing
    logger for the rest of the session, breaking later tests that assert on logs.
    """
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
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


@pytest.fixture
def seeded_database(app_database: str) -> str:
    """`app_database` with the reference tables seeded, as the application boots.

    Needed by the setup endpoints, which read the persona/scenario tables (ADR 0041).
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
        active=True,
        visibility=db_models.VISIBILITY_PUBLIC,
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


def persist(  # pylint: disable=too-many-arguments
    *,
    extern_id: uuid.UUID | None = None,
    reason: str = "user",
    turns: list[Turn] | None = None,
    persona_key: str = PERSONA_KEY,
    # Named for the same reason `persona_key` is: a test that runs against the
    # *seeded* reference data rather than against `reference_data`'s two hand-
    # written rows has to say which rows the Session points at.
    scenario_key: str = SCENARIO_KEY,
    subject: str = TEST_AUTH.sub,
    started_at: datetime = SESSION_STARTED,
) -> uuid.UUID:
    """Write a Session through the real write path; returns its extern_id.

    Needs `app_database`, since persist_session() opens its own session_scope().
    `started_at` defaults to a fixed instant for reproducibility.
    """
    # Imported here, not at module scope: importing the write path pulls in
    # the feedback stack, which a collection-time import should not need.
    from backend import consent  # pylint: disable=import-outside-toplevel
    from backend.session import persistence  # pylint: disable=import-outside-toplevel

    # The write path refuses without it (ADR 0066), and it checks inside its own
    # transaction, so it cannot be granted from a test's `db_session`. A stored
    # Session always has a decision behind it in reality; a test that wants the
    # refusal asks for it explicitly (tests/test_consent.py).
    with session_scope() as db:
        if not consent.allows_storage(subject, db=db):
            consent.record_decision(db, subject, granted=True)

    # The value object the write path receives carries the row's `extern_id` as
    # `.id` since ADR 0058, so resolve it from the reference row the fixture
    # inserted. A `persona_key` the fixture did not write yields a random id,
    # which exercises the LookupError path.
    with session_scope() as db:
        prow = db.query(db_models.Persona).filter_by(key=persona_key).one_or_none()
        srow = db.query(db_models.Scenario).filter_by(key=scenario_key).one_or_none()
    persona = replace(TEST_PERSONAS[0], id=str(prow.extern_id) if prow else str(uuid.uuid4()))
    scenario = replace(TEST_SCENARIOS[0], id=str(srow.extern_id) if srow else str(uuid.uuid4()))
    extern_id = extern_id or uuid.uuid4()
    persistence.persist_session(persistence.FinishedCall(
        extern_id=extern_id,
        subject_id=subject,
        persona=persona,
        scenario=scenario,
        turns=turns if turns is not None else [],
        started_at=started_at,
        reason=reason,
    ))
    return extern_id


@pytest.fixture
async def api_client(app_database: str) -> AsyncIterator[httpx.AsyncClient]:  # pylint: disable=unused-argument
    """The FastAPI app, wired to this test's throwaway database via `app_database`.

    Uses httpx's ASGI transport, not Starlette's TestClient: the pinned starlette
    (0.35) passes `app=` to httpx.Client, which httpx 0.28 rejects.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


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


# One finished exchange with speech durations filled in, so pace (a rate over
# phonation) is measured. Three user utterances, because the reverse and
# follow-up routes refuse fewer (`MIN_USER_UTTERANCES`).
DRAFTED_FROM_TURNS = [
    Turn(seq=1, persona_text="Brandt hier.", persona_offset_ms=0, persona_end_ms=1500),
    Turn(seq=2, user_text="Guten Tag, was kann ich für Sie tun?",
         user_offset_ms=1800, user_end_ms=3400,
         user_speech_ms=1600, user_phonation_ms=1300,
         persona_text="Der Preis ist zu hoch.",
         persona_offset_ms=3700, persona_end_ms=5000),
    Turn(seq=3, user_text="Darüber können wir reden. Was wäre für Sie vertretbar?",
         user_offset_ms=5300, user_end_ms=7600,
         user_speech_ms=2300, user_phonation_ms=1900,
         persona_text="Zehn Prozent weniger.",
         persona_offset_ms=7900, persona_end_ms=9000),
    Turn(seq=4, user_text="Das prüfe ich und melde mich morgen bei Ihnen.",
         user_offset_ms=9300, user_end_ms=11400,
         user_speech_ms=2100, user_phonation_ms=1700,
         persona_text="Gut, danke.",
         persona_offset_ms=11700, persona_end_ms=12500),
]


def a_finished_session(
    turns=None, subject: str | None = None, started_at: datetime | None = None
) -> uuid.UUID:
    """One Session written through the real write path, default `DRAFTED_FROM_TURNS`.

    `subject` sets another owner (ownership refusals); `started_at` moves it in time
    (retention). Omitted rather than passed as None, so `persist` keeps its defaults.
    """
    kwargs: dict = {}
    if subject is not None:
        kwargs["subject"] = subject
    if started_at is not None:
        kwargs["started_at"] = started_at
    return persist(turns=DRAFTED_FROM_TURNS if turns is None else turns, **kwargs)
