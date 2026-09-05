from types import SimpleNamespace

from backend import worker


def test_work_horse_killed_marks_feedback_job_failed(monkeypatch) -> None:
    marked = []

    monkeypatch.setattr(
        worker.persistence,
        "mark_feedback_job_failed",
        lambda session_id, error_text: marked.append(
            (session_id, error_text)
        ),
    )

    job = SimpleNamespace(
        args=(42,),
        id="test-job",
    )

    worker._work_horse_killed(
        job,
        1234,
        9,
        None,
    )

    assert marked[0][0] == 42
    assert "pid=1234" in marked[0][1]
    assert "exit_status=9" in marked[0][1]
