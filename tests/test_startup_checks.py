"""The startup backend checks (ADR 0016, ADR 0074).

The wrap-up model is the one worth a test. It is reached only from the RQ
worker, so a name that does not resolve breaks nothing a caller would notice --
the calls keep working and the wrap-ups never arrive. The check exists so that
shows up at boot; these pin that it is wired when, and only when, the wrap-up
runs on a model of its own.
"""

import importlib

import pytest

from backend.clients import config, health

# pylint: disable=missing-function-docstring,protected-access


@pytest.fixture(name="checks_for")
def _checks_for(monkeypatch):
    """`health._CHECKS` as it would be built for a given wrap-up model.

    `_CHECKS` is assembled at import from module constants, so the branch can
    only be reached by reloading -- and the reload has to be undone, or every
    later test in the session sees this one's config.
    """
    def build(feedback_model: str) -> dict:
        monkeypatch.setattr(config, "LLM_FEEDBACK_MODEL", feedback_model)
        return importlib.reload(health)._CHECKS.copy()
    yield build
    monkeypatch.undo()
    importlib.reload(health)


def test_only_three_checks_while_one_model_does_both(checks_for):
    checks = checks_for(config.LLM_MODEL)
    assert set(checks) == {"STT", "LLM", "TTS"}, "a second identical request would learn nothing"


def test_the_wrap_up_model_is_checked_when_it_is_its_own(checks_for):
    checks = checks_for("some-other-model")
    assert set(checks) == {"STT", "LLM", "TTS", "LLM (wrap-up)"}
    assert checks["LLM (wrap-up)"][1] == "some-other-model", "reported under its own name"


async def test_the_wrap_up_check_asks_the_way_its_callers_do(monkeypatch):
    """`think=True`, because the thinking level is the parameter most likely to
    be wrong for a model and an unsupported one is a 400 that names nothing."""
    seen = {}

    async def fake_complete(messages, **kwargs):
        seen.update(kwargs, messages=messages)
        return "ok"

    monkeypatch.setattr(health.llm, "complete", fake_complete)
    await health._check_feedback_llm()

    assert seen["think"] is True
    assert seen["messages"], "a real request, not an empty one"
