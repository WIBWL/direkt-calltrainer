"""What the boot check reports when a backend does not answer.

Covers:
  ADR 0074  dialogue generation on Gemini; the models are named in `.env` and
            a wrong one has to surface at boot rather than mid-call
  ADR 0011  the gateway's own model, checked the same way

The check only logs -- `lifespan` boots either way -- so its whole value is the
sentence it writes. Two ways of losing that sentence are pinned here, both seen
in a real log: `asyncio.wait_for`'s TimeoutError carries no message, so the line
ended in a bare dash; and the OpenAI client retried a 429 twice with backoff
*inside* the check's own deadline, so a rate-limited model never got to report
its rate limit and timed out instead.

The backends are faked (`conftest.py`); nothing here reaches a network.
"""
import asyncio
import logging

import httpx
import pytest
from openai import OpenAIError, RateLimitError

from backend.clients import health, llm

# pylint: disable=missing-function-docstring,redefined-outer-name
# pylint: disable=protected-access  # the check's internals are the unit here
# pylint: disable=unused-argument  # a fixture taken for its patching, not its value


def _rate_limit() -> RateLimitError:
    return RateLimitError(
        "429 RESOURCE_EXHAUSTED: quota exceeded",
        response=httpx.Response(429, request=httpx.Request("POST", "http://gemini")),
        body=None,
    )


@pytest.fixture
def recording_client(monkeypatch):
    """Stands in for the OpenAI client and records the per-request options the
    check asks for. Every request raises 429 — the case this is all about."""
    options: dict = {}

    class Completions:
        async def create(self, **_kwargs):
            raise _rate_limit()

    class Chat:
        completions = Completions()

    class Client:
        chat = Chat()

        def with_options(self, **kwargs):
            options.update(kwargs)
            return self

    monkeypatch.setattr(llm, "LLM_CLIENT", Client())
    return options


async def test_the_llm_check_asks_for_a_single_attempt(recording_client):
    """Retrying is right for a Turn and wrong for a probe: the retries run
    inside the probe's deadline and turn a 429 into a timeout."""
    with pytest.raises(RateLimitError):
        await health._check_llm()
    assert recording_client == {"max_retries": 0}


async def test_the_wrap_up_check_asks_for_one_too(recording_client):
    with pytest.raises(RateLimitError):
        await health._check_feedback_llm()
    assert recording_client == {"max_retries": 0}


async def test_a_rate_limited_model_reports_its_own_429(recording_client, caplog):
    caplog.set_level(logging.ERROR, logger="backend.clients.health")
    assert await health._run_check("LLM", health._check_llm, "gemini-3.5-flash-lite") is False
    line = caplog.records[-1].getMessage()
    assert "RESOURCE_EXHAUSTED" in line
    assert "gemini-3.5-flash-lite" in line


async def test_a_timeout_says_so_instead_of_trailing_off(monkeypatch, caplog):
    """`str(TimeoutError())` is "", which is how this line came to end in a
    dash and nothing — indistinguishable from an answer that was empty."""
    monkeypatch.setattr(health, "_CHECK_TIMEOUT", 0.01)
    caplog.set_level(logging.ERROR, logger="backend.clients.health")

    async def never():
        await asyncio.sleep(5)

    assert await health._run_check("LLM", never, "some-model") is False
    line = caplog.records[-1].getMessage()
    assert "no answer within" in line
    assert not line.rstrip().endswith("—")


async def test_an_error_with_no_message_falls_back_to_its_class(caplog):
    """OSError() stringifies to "" as well; a class name beats a blank."""
    caplog.set_level(logging.ERROR, logger="backend.clients.health")

    async def blank():
        raise OSError()

    assert await health._run_check("STT", blank, "whisper") is False
    assert caplog.records[-1].getMessage().endswith("OSError")


async def test_a_backend_that_answers_passes(caplog):
    caplog.set_level(logging.INFO, logger="backend.clients.health")

    async def fine():
        return None

    assert await health._run_check("TTS", fine, "kugelaudio") is True
    assert "OK" in caplog.records[-1].getMessage()


async def test_a_reported_failure_is_counted_not_raised(monkeypatch, caplog):
    """`check_backends` never raises — it runs from `lifespan`, which logs a
    dead dependency rather than failing the boot."""
    caplog.set_level(logging.ERROR, logger="backend.clients.health")

    async def down():
        raise OpenAIError("model not found")

    async def fine():
        return None

    monkeypatch.setattr(health, "_CHECKS", {"LLM": (down, "m"), "STT": (fine, "s")})
    assert await health.check_backends() is False
    assert "1 of 2 backends failing" in caplog.records[-1].getMessage()
