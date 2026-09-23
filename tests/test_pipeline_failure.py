"""Pipeline fault tolerance.

Covers ADR 0016 (one retry, then graceful end) as reinterpreted per leg by
ADR 0033 / ADR 0044:
  * STT: one retry; a second failure -> `stt_failed`, turn ends
  * LLM: retried only while nothing has been sent; -> `llm_failed`
  * TTS: one backend and no fallback since ADR 0103, so any failure to
    synthesise a chunk -> `tts_failed`. A failure *after* audio has been sent
    ends the turn for a second reason (a fresh synth would diverge from what
    was heard).
The one retry ADR 0016 grants is per leg: STT and the LLM have one, and the
voice does not, because a retry there is a second request on a pooled socket
whose state the first one left in doubt (ADR 0044).
"""

import pytest

from backend.session.models import Failed
from backend.session.orchestrator import SessionOrchestrator
from tests.conftest import audio_chunks, collect, completed, failure

# pylint: disable=missing-function-docstring,redefined-outer-name


@pytest.fixture
def orch(persona, scenario):
    return SessionOrchestrator(persona, scenario)


async def test_single_transient_stt_failure_is_retried_and_absorbed(orch, fake_pipeline):
    fake_pipeline.stt.fail_times = 1
    fake_pipeline.stt.transcripts = ["Hat beim zweiten Versuch geklappt."]
    fake_pipeline.llm.replies = ["Alles gut, verstanden."]

    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    assert failure(events) is None
    assert completed(events) is not None
    assert len(fake_pipeline.stt.calls) == 2  # first failed, retry succeeded


async def test_persistent_stt_failure_ends_the_turn_with_stt_failed(orch, fake_pipeline):
    fake_pipeline.stt.fail_times = 5  # both attempts fail

    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    fail = failure(events)
    assert fail is not None and fail.code == "stt_failed"
    assert completed(events) is None
    assert len(fake_pipeline.stt.calls) == 2  # exactly one retry, no more


async def test_persistent_llm_failure_ends_the_turn_with_llm_failed(orch, fake_pipeline):
    fake_pipeline.stt.transcripts = ["Bitte antworten Sie mir."]
    fake_pipeline.llm.fail_times = 5

    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    fail = failure(events)
    assert fail is not None and fail.code == "llm_failed"


async def test_transient_llm_failure_before_any_audio_is_retried(orch, fake_pipeline):
    fake_pipeline.stt.transcripts = ["Bitte antworten Sie mir."]
    fake_pipeline.llm.fail_times = 1
    fake_pipeline.llm.replies = ["Zweiter Anlauf, jetzt klappt es."]

    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    assert failure(events) is None
    assert audio_chunks(events)


async def test_persistent_tts_failure_ends_the_turn_with_tts_failed(orch, fake_pipeline):
    fake_pipeline.stt.transcripts = ["Sagen Sie etwas."]
    fake_pipeline.llm.replies = ["Diese Antwort kann nicht synthetisiert werden."]
    fake_pipeline.tts.fail_times = 5

    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    fail = failure(events)
    assert fail is not None and fail.code == "tts_failed"


async def test_a_single_tts_failure_ends_the_turn_too(orch, fake_pipeline):
    """There is nothing behind KugelAudio to absorb a blip (ADR 0103): one
    failed chunk is a failed Turn, and it says so instead of being spoken in
    another voice."""
    fake_pipeline.stt.transcripts = ["Sagen Sie etwas."]
    fake_pipeline.llm.replies = ["Kurze Antwort."]
    fake_pipeline.tts.fail_times = 1

    events = await collect(orch.run_turn(b"a", "turn.webm", "audio/webm"))

    fail = failure(events)
    assert fail is not None and fail.code == "tts_failed"
    assert len(fake_pipeline.tts.calls) == 1, "one attempt, no second backend"


def test_wire_error_codes_are_the_three_known_legs():
    """The Failed event's code vocabulary the client (protocol.ts) expects."""
    codes = Failed.__annotations__["code"]
    assert set(getattr(codes, "__args__", ())) == {"stt_failed", "llm_failed", "tts_failed"}
