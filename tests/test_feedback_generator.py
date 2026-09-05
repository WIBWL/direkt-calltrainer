from backend.feedback.generator import _ask
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from backend.feedback import generator


async def test_ask_retries_after_llm_request_failure(monkeypatch) -> None:
    calls = 0

    async def fake_complete(_messages):
        nonlocal calls
        calls += 1

        if calls == 1:
            raise RuntimeError("temporary LLM failure")

        return (
            '{"summary": "Feedback erzeugt.", '
            '"phase_language": "", '
            '"strengths": [], '
            '"improvements": []}'
        )

    monkeypatch.setattr(
        "backend.feedback.generator.llm.complete",
        fake_complete,
    )

    wrapup = await _ask("Test dossier", "English")

    assert calls == 2
    assert wrapup.summary == "Feedback erzeugt."


async def test_generate_marks_job_failed_when_storage_fails(monkeypatch) -> None:
    marks = []
    session = SimpleNamespace(language_code="de")

    class FakeDb:
        def get(self, _model, _session_id):
            return session

    @contextmanager
    def fake_session_scope():
        yield FakeDb()

    monkeypatch.setattr(generator, "session_scope", fake_session_scope)

    monkeypatch.setattr(
        generator,
        "_mark",
        lambda _db, _session_id, status, error_text=None: marks.append(
            (status, error_text)
        ),
    )

    monkeypatch.setattr(
        generator,
        "_dossier",
        lambda _session: ("test dossier", {1}),
    )

    async def fake_ask(_dossier, _language):
        return generator._Wrapup(summary="Feedback erzeugt.")

    monkeypatch.setattr(generator, "_ask", fake_ask)

    def fail_store(_db, _session_id, _wrapup, _turn_ids):
        raise RuntimeError("storage failed")

    monkeypatch.setattr(generator, "_store", fail_store)

    with pytest.raises(RuntimeError, match="storage failed"):
        await generator._generate(1)

    assert marks[0] == ("running", None)
    assert marks[-1][0] == "failed"
    assert "storage failed" in marks[-1][1]
