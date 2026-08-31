"""Shared test fixtures.

The backend reads a handful of environment variables at import time
(`backend/clients/config.py`), so they are set here *before* any backend
module is imported. Values are dummies: no test in this suite makes a real
network call — every pipeline backend (STT / LLM / TTS) is faked.

`DEBUG=true` keeps TTS config fully offline (no KugelAudio client is
constructed); the KugelAudio-default / EFRE-fallback dispatch is still
covered in `test_tts_fallback.py` by patching the tts module directly.
"""

# The env vars below must be set before backend imports run, so those imports
# deliberately sit after this block.
# pylint: disable=wrong-import-position,missing-function-docstring
# pylint: disable=too-few-public-methods,redefined-outer-name

import importlib.util
import os
import sys
from pathlib import Path

os.environ.setdefault("EFRE_URL", "http://efre.test.invalid")
os.environ.setdefault("EFRE_API_KEY", "test-efre-key")
os.environ.setdefault("STT_MODEL", "test-stt-model")
os.environ.setdefault("LLM_MODEL", "test-llm-model")
os.environ.setdefault("TTS_MODEL", "test-tts-model")
os.environ.setdefault("KUGELAUDIO_MODEL", "test-kugelaudio-model")
os.environ.setdefault("KUGELAUDIO_API_KEY", "test-kugelaudio-key")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

import pytest  # noqa: E402
from kugelaudio.exceptions import KugelAudioError  # noqa: E402
from openai import OpenAIError  # noqa: E402

from backend import library  # noqa: E402
from backend.clients import llm, stt, tts  # noqa: E402
from backend.personas import Persona, PersonaVoice  # noqa: E402
from backend.scenarios import Scenario  # noqa: E402
from backend.session.models import AudioChunk, Failed, StateChanged, TurnCompleted  # noqa: E402

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
    """Import `scripts/seed_reference_data.py`, which is a script, not a
    package. ADR 0041 makes it the source of the library's initial content, so
    tests about *what* the library ships read it from here. It only touches the
    environment inside `main()`, so importing it needs no database and no
    `.env`."""
    path = REPO / "scripts" / "seed_reference_data.py"
    spec = importlib.util.spec_from_file_location("seed_reference_data", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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
    monkeypatch.setattr(library, "list_personas", lambda: list(TEST_PERSONAS))
    monkeypatch.setattr(library, "list_scenarios", lambda: list(TEST_SCENARIOS))
    monkeypatch.setattr(library, "get_persona", by_id.get)
    monkeypatch.setattr(library, "get_scenario", by_key.get)
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

    `synthesize_stream` mimics the real KugelAudio->EFRE fallback as a
    two-attempt sequence: a `fail_times` of 1 is "KugelAudio blipped, EFRE
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
        for _ in range(2):  # KugelAudio attempt, then the EFRE fallback
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
