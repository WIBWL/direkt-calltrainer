"""Backend fixtures: library doubles, the faked pipeline, auth and the real write path."""

# The environment must be set before the packages are imported.
# pylint: disable=wrong-import-position,missing-function-docstring
# pylint: disable=too-few-public-methods,redefined-outer-name

import os
import uuid
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import httpx
import pytest
from kugelaudio.exceptions import KugelAudioError
from openai import OpenAIError

# Imported first as well as registered: pytest registers plugins only after this
# module ran, and the fixtures set the environment the imports below read.
pytest.register_assert_rewrite("shared.tests.fixtures")
from shared.tests.fixtures import PERSONA_KEY, SCENARIO_KEY, SESSION_STARTED  # noqa: E402

pytest_plugins = ["shared.tests.fixtures"]

os.environ.setdefault("STT_MODEL", "test-stt-model")
os.environ.setdefault("KUGELAUDIO_MODEL", "test-kugelaudio-model")
os.environ.setdefault("KUGELAUDIO_API_KEY", "test-kugelaudio-key")
os.environ.setdefault("OIDC_ISSUER", "http://keycloak.test.invalid/realms/direkt")

from shared.clients import llm  # noqa: E402
# Namespaced: `Persona`/`Scenario` below are the value objects.
from shared.db import models as db_models  # noqa: E402
from shared.db.session import session_scope  # noqa: E402
from shared.turn import Turn  # noqa: E402
from backend import auth, library, limits  # noqa: E402
from backend.app import app  # noqa: E402
from backend.clients import stt, tts  # noqa: E402
from backend.personas import Persona, PersonaVoice  # noqa: E402
from backend.scenarios import Scenario  # noqa: E402
from backend.session.events import AudioChunk, Failed, StateChanged, TurnCompleted  # noqa: E402

# Test doubles of the library, so most tests need no database; the seed is
# checked in test_persona_scenario_library.py.
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


REPO = Path(__file__).resolve().parents[2]


def load_seed_module():
    from shared.db import seed_data  # pylint: disable=import-outside-toplevel

    return seed_data


# A caller the role gate admits.
TEST_AUTH = auth.AuthContext(sub="test-subject", roles=[auth.REQUIRED_ROLE], token="test-token")


@pytest.fixture
def auth_ctx():
    return TEST_AUTH


@pytest.fixture(autouse=True)
def _fresh_limits(monkeypatch):
    # The caps count in-process and every test calls as TEST_AUTH.
    open_calls, summaries, drafts = limits.fresh()
    monkeypatch.setattr(limits, "OPEN_CALLS", open_calls)
    monkeypatch.setattr(limits, "DOCUMENT_SUMMARIES", summaries)
    monkeypatch.setattr(limits, "SCENARIO_DRAFTS", drafts)


@pytest.fixture(autouse=True)
def _override_auth():
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
    """Serve the test doubles; patched on `library`, where both call sites look."""
    by_id = {p.id: p for p in TEST_PERSONAS}
    by_key = {s.id: s for s in TEST_SCENARIOS}
    # The doubles ignore visibility scoping; test_authored_content.py tests the
    # real query.
    monkeypatch.setattr(library, "list_personas", lambda: list(TEST_PERSONAS))
    monkeypatch.setattr(library, "list_scenarios", lambda subject, tenant_id=1: list(TEST_SCENARIOS))
    monkeypatch.setattr(library, "get_persona", by_id.get)
    monkeypatch.setattr(library, "get_scenario", lambda extern_id, subject=None, tenant_id=1: by_key.get(extern_id))
    monkeypatch.setattr("backend.api.session_ws.resolve_tenant_id", lambda auth: 1)
    return library


class FakeLLM:
    """`.replies` stream as token deltas; `.fail_times` fails the first N calls."""

    def __init__(self, replies=None):
        self.replies = list(replies or ["Alles klar, danke."])
        self.calls = []
        self.fail_times = 0
        # `complete` is the notes refresh (ADR 0071); empty by default, so the
        # notes stay off.
        self.states = []
        self.state_calls = []
        self.state_fail_times = 0

    async def complete(self, messages, **_kwargs):
        self.state_calls.append(messages)
        if self.state_fail_times > 0:
            self.state_fail_times -= 1
            raise OpenAIError("simulated notes failure")
        return self.states.pop(0) if self.states else ""

    # `**_kwargs` keeps the real signature: the boot check passes `retries`.
    def stream_reply(self, messages, **_kwargs):
        self.calls.append(messages)

        async def _gen():
            if self.fail_times > 0:
                self.fail_times -= 1
                raise OpenAIError("simulated LLM failure")
            reply = self.replies.pop(0) if self.replies else ""
            for i, word in enumerate(reply.split(" ")):
                yield word if i == 0 else " " + word

        return _gen()


class FakeSTT:
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
    """`fail_times` raises KugelAudioError; `.hang` parks synthesis;
    `.chunks_per_call` sets sub-chunks per chunk."""

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
    llm_fake = FakeLLM()
    stt_fake = FakeSTT()
    tts_fake = FakeTTS()

    monkeypatch.setattr(llm, "stream_reply", llm_fake.stream_reply)
    monkeypatch.setattr(llm, "complete", llm_fake.complete)
    monkeypatch.setattr(stt, "transcribe", stt_fake.transcribe)
    monkeypatch.setattr(tts, "synthesize_stream", tts_fake.synthesize_stream)
    monkeypatch.setattr(tts, "synthesize", tts_fake.synthesize)

    class Pipeline:
        llm = llm_fake
        stt = stt_fake
        tts = tts_fake

    return Pipeline()


async def collect(turn_events):
    return [event async for event in turn_events]


def states(events):
    return [e.state for e in events if isinstance(e, StateChanged)]


def audio_chunks(events):
    return [e for e in events if isinstance(e, AudioChunk)]


def completed(events):
    return next((e for e in events if isinstance(e, TurnCompleted)), None)


def failure(events):
    return next((e for e in events if isinstance(e, Failed)), None)


@pytest.fixture
def seeded_database(app_database: str) -> str:
    """`app_database` seeded as the application boots."""
    # Imported here so collection never needs the environment.
    from backend.db.provision import seed  # pylint: disable=import-outside-toplevel

    with session_scope() as db:
        seed(db)
    return app_database


def persist(  # pylint: disable=too-many-arguments
    *,
    extern_id: uuid.UUID | None = None,
    reason: str = "user",
    turns: list[Turn] | None = None,
    persona_key: str = PERSONA_KEY,
    scenario_key: str = SCENARIO_KEY,
    subject: str = TEST_AUTH.sub,
    started_at: datetime = SESSION_STARTED,
) -> uuid.UUID:
    """Write a Session through the real write path; returns its extern_id."""
    # Imported here: the write path pulls in the feedback stack.
    from backend import consent  # pylint: disable=import-outside-toplevel
    from backend.session import persistence  # pylint: disable=import-outside-toplevel

    # The write path refuses without consent (ADR 0066), checked in its own
    # transaction; test_consent.py asks for the refusal explicitly.
    with session_scope() as db:
        if not consent.allows_storage(subject, db=db):
            consent.record_decision(db, subject, granted=True)

    # An unknown `persona_key` yields a random id, exercising the LookupError path.
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
    """httpx's ASGI transport: Starlette's TestClient breaks on httpx 0.28."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


# Three user utterances: the reverse and follow-up routes refuse fewer.
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
    """One Session through the real write path."""
    kwargs: dict = {}
    if subject is not None:
        kwargs["subject"] = subject
    if started_at is not None:
        kwargs["started_at"] = started_at
    return persist(turns=DRAFTED_FROM_TURNS if turns is None else turns, **kwargs)
