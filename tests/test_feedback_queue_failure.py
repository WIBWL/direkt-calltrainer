import uuid
from datetime import datetime
from types import SimpleNamespace

from backend.api.session_ws import _record
from backend.feedback import queue
from backend.session import persistence


async def test_record_marks_feedback_job_failed_when_enqueue_fails(
    monkeypatch,
) -> None:
    marked = []

    monkeypatch.setattr(
        persistence,
        "persist_session",
        lambda *_args: 42,
    )

    def fail_enqueue(_session_id):
        raise RuntimeError("redis unavailable")

    monkeypatch.setattr(queue, "enqueue_feedback", fail_enqueue)

    monkeypatch.setattr(
        persistence,
        "mark_feedback_job_failed",
        lambda session_id, error_text: marked.append(
            (session_id, error_text)
        ),
    )

    await _record(
        uuid.uuid4(),
        "test-subject",
        object(),
        object(),
        SimpleNamespace(turns=[]),
        datetime.now(),
        "user",
    )

    assert marked == [(42, "redis unavailable")]
