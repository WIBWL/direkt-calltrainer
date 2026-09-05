"""The feedback job's lifecycle, from the Session being written to a wrap-up.

Covers:
  F-53/F-42  the post-call wrap-up, which is what this job produces
  ADR 0019  the job is queued after the call, in Redis, and run by a separate
            worker process -- two systems, so two writes that can disagree
  ADR 0032  `analysis_job` carries the status, which ADR 0050's session
            endpoint serves as the Session's `status`. The post-call screen
            polls on it, so a row stranded at "queued" or "running" is a
            spinner that stops only on the client's own timeout.

Against a real database, because the thing under test *is* the row: a test that
asserts a mock was called would pass even if the transaction never committed.
Only the model call is stubbed -- ADR 0011's gateway is not a test dependency.
"""

import uuid
from dataclasses import replace
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session as DbSession

from backend.api.session_ws import _record
from backend.db.models import AnalysisJob, Session
from backend.db.session import session_scope
from backend.feedback import generator, jobs, queue
from backend.session.models import Turn
from tests.conftest import (
    PERSONA_KEY,
    SCENARIO_KEY,
    SESSION_STARTED,
    TEST_PERSONAS,
    TEST_SCENARIOS,
    persist,
)

pytestmark = pytest.mark.usefixtures("app_database", "reference_data")

# The job state machine and the generator's internals are the units under test.
# pylint: disable=protected-access


def _turns() -> list[Turn]:
    """One exchange: enough of a Session to write a wrap-up about."""
    return [
        Turn(seq=1, persona_text="Brandt hier.", persona_offset_ms=0, persona_end_ms=1_500),
        Turn(
            seq=2,
            user_text="Guten Tag!",
            user_offset_ms=1_800,
            user_end_ms=2_700,
            user_speech_ms=900,
            user_phonation_ms=700,
            persona_text="Zu teuer.",
            persona_offset_ms=3_000,
            persona_end_ms=4_100,
        ),
    ]


def _persisted(db: DbSession) -> int:
    """A written Session's internal id -- what the queue payload carries."""
    persist(turns=_turns())
    return db.query(Session).one().session_id


def _job(db: DbSession) -> AnalysisJob:
    db.expire_all()
    return db.query(AnalysisJob).one()


def test_a_written_session_starts_with_a_queued_job(db_session: DbSession) -> None:
    """ADR 0032. The row is created in the Session's transaction, so the first
    status the client polls is "queued" -- never a missing row, which
    `_feedback_status` reports as failed."""
    _persisted(db_session)

    assert _job(db_session).status == "queued"


async def test_a_finished_run_marks_the_job_done(db_session: DbSession, monkeypatch) -> None:
    """The happy path, so the failure paths below cannot pass by marking
    everything failed."""
    session_id = _persisted(db_session)

    async def wrapup(_dossier, _language):
        return generator._Wrapup(summary="Sie haben ruhig und klar gesprochen.")

    monkeypatch.setattr(generator, "_ask", wrapup)

    await generator._generate(session_id)

    job = _job(db_session)
    assert job.status == "done"
    assert job.error_text is None
    assert job.attempts == 1


async def test_a_storage_failure_marks_the_job_failed(
    db_session: DbSession, monkeypatch
) -> None:
    """The wrap-up is generated and then written, and the write can fail on its
    own -- which has to close the row rather than leave it at "running"."""
    session_id = _persisted(db_session)

    async def wrapup(_dossier, _language):
        return generator._Wrapup(summary="Sie haben ruhig und klar gesprochen.")

    def fail_store(_db, _session_id, _wrapup, _turn_ids):
        raise RuntimeError("feedback_point insert failed")

    monkeypatch.setattr(generator, "_ask", wrapup)
    monkeypatch.setattr(generator, "_store", fail_store)

    # Re-raised on purpose: RQ has to see the job fail, or it counts as done.
    with pytest.raises(RuntimeError, match="feedback_point insert failed"):
        await generator._generate(session_id)

    job = _job(db_session)
    assert job.status == "failed"
    assert "feedback_point insert failed" in job.error_text


async def test_a_model_failure_marks_the_job_failed(
    db_session: DbSession, monkeypatch
) -> None:
    """The model call is the other way in: a gateway that never answers closes
    the row too."""
    session_id = _persisted(db_session)

    async def unreachable(_dossier, _language):
        raise RuntimeError("gateway unreachable")

    monkeypatch.setattr(generator, "_ask", unreachable)

    with pytest.raises(RuntimeError, match="gateway unreachable"):
        await generator._generate(session_id)

    assert _job(db_session).status == "failed"


async def test_a_session_that_was_never_written_leaves_no_job_behind(
    db_session: DbSession,
) -> None:
    """`jobs.mark` creates the row where it finds none, so a job id pointing at
    nothing has to stop before it rather than leave a dangling row."""
    with pytest.raises(LookupError):
        await generator._generate(4_711)

    assert db_session.query(AnalysisJob).count() == 0


async def test_a_failed_enqueue_marks_the_job_failed(
    db_session: DbSession, monkeypatch
) -> None:
    """ADR 0019's two writes: the row is committed with the Session, the queue
    entry goes to Redis afterwards. When Redis is unreachable the work never
    happens, and a row saying "queued" claims otherwise.

    The transcript reaches the user either way -- `_record` runs after the call
    is over and is not allowed to raise.
    """
    def unreachable(_session_id):
        raise RuntimeError("redis unavailable")

    monkeypatch.setattr(queue, "enqueue_feedback", unreachable)

    await _record(
        uuid.uuid4(),
        "test-subject",
        replace(TEST_PERSONAS[0], id=PERSONA_KEY),
        replace(TEST_SCENARIOS[0], id=SCENARIO_KEY),
        SimpleNamespace(turns=_turns()),
        SESSION_STARTED,
        "user",
    )

    job = _job(db_session)
    assert job.status == "failed"
    assert "redis unavailable" in job.error_text


def test_a_late_failure_does_not_overwrite_a_finished_job(db_session: DbSession) -> None:
    """`jobs.mark_failed` writes from outside the process running the job, so by
    the time it commits the wrap-up may already be on the user's screen."""
    session_id = _persisted(db_session)
    job = _job(db_session)
    job.status = "done"
    db_session.commit()

    jobs.mark_failed(session_id, "late failure")

    job = _job(db_session)
    assert job.status == "done"
    assert job.error_text is None


def test_the_worker_may_still_move_its_own_running_job(db_session: DbSession) -> None:
    """The counterpart to the guard above: `jobs.mark` *is* the process running
    the job, so it overwrites whatever state it finds."""
    session_id = _persisted(db_session)

    with session_scope() as db:
        jobs.mark(db, session_id, "running")
        jobs.mark(db, session_id, "done")

    assert _job(db_session).status == "done"


def test_marking_a_session_without_a_job_is_a_lookup_error(db_session: DbSession) -> None:
    """The out-of-band writer is reached only after the Session was persisted
    with its row, so a missing one is a bug rather than a state to absorb."""
    _persisted(db_session)

    with pytest.raises(LookupError):
        jobs.mark_failed(4_711, "no such session")
