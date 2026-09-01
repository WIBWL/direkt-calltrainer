"""Shared test fixtures.

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
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("OIDC_ISSUER", "http://keycloak.test.invalid/realms/direkt")

import pytest  # noqa: E402
from kugelaudio.exceptions import KugelAudioError  # noqa: E402
from openai import OpenAIError  # noqa: E402

from backend import auth  # noqa: E402
from backend.app import app  # noqa: E402
from backend.clients import llm, stt, tts  # noqa: E402
from backend.personas import PERSONAS  # noqa: E402
from backend.scenarios import SCENARIOS  # noqa: E402
from backend.session.models import AudioChunk, Failed, StateChanged, TurnCompleted  # noqa: E402

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
    return PERSONAS[0]


@pytest.fixture
def scenario():
    return SCENARIOS[0]


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
