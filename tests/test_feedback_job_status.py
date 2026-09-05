"""The AnalysisJob row behind the post-call poll (ADR 0032, F-09, F-10).

The wrap-up is generated asynchronously (ADR 0018/0019), so this row is the
only thing that tells the finished-call screen whether to keep polling: it is
written `queued` with the Session (ADR 0034), moved by the worker, and read
back by `GET /api/sessions/{extern_id}` as `status` (ADR 0050).

That makes it a quiet failure path. If a transition stops being written, the
wrap-up still lands in the database and the client still polls -- it just gives
up on its own deadline and shows the user a failure that did not happen. These
tests pin the whole lifecycle, including the two cases where the row would
otherwise describe a job that no longer exists.

Postgres has to be running (`docker compose up -d db`); without it the database
fixtures skip.
"""

import json
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy.orm import Session as DbSession

from backend.clients import llm
from backend.db.models import AnalysisJob, Feedback, Session
from backend.feedback.generator import generate_feedback
from backend.feedback.queue import JOB_TIMEOUT_S
from backend.session import persistence
from backend.session.models import Turn
from tests.conftest import persist

pytestmark = pytest.mark.usefixtures("reference_data")

# What the stubbed model returns; the shape `_Wrapup` validates. The keys are
# English since ADR 0057 -- with the old German ones the validation fails, `_ask`
# retries once, and the narrative-only fallback still stores a Feedback row, so
# a test that only counts rows stays green while exercising the wrong path.
_SUMMARY = "Sachliches Gespräch mit klarer Bedarfsfrage."
_REPLY = json.dumps({
    "summary": _SUMMARY,
    "phase_language": "Der Ton bleibt über alle Phasen gleich sachlich.",
    "strengths": [{"text": "Klare Nachfrage."}],
    "improvements": [{"text": "Mehr Pausen lassen."}],
})


def _store(extern_id: uuid.UUID | None = None) -> uuid.UUID:
    """One finished Session, written through the real path."""
    return persist(
        extern_id=extern_id,
        turns=[
            Turn(seq=1, persona_text="Brandt hier.",
                 persona_offset_ms=0, persona_end_ms=1500),
            Turn(seq=2,
                 user_text="Guten Tag, kurz zu Ihrem Vertrag.",
                 user_offset_ms=1800, user_end_ms=3200,
                 persona_text="Zu teuer.",
                 persona_offset_ms=3500, persona_end_ms=4600),
        ],
    )


def _job(db: DbSession, session_id: int) -> AnalysisJob:
    """This Session's feedback job, read fresh -- the writer used its own
    session, so anything already in this one's identity map is stale."""
    db.expire_all()
    return db.query(AnalysisJob).filter_by(session_id=session_id, kind="feedback").one()


def _stub_model(monkeypatch, reply) -> None:
    """Replace the wrap-up's model call. `reply` is the text to answer with, or
    a callable invoked instead (to observe state, or to fail)."""
    async def complete(messages: list[dict[str, str]]) -> str:
        return reply(messages) if callable(reply) else reply

    monkeypatch.setattr(llm, "complete", complete)


def test_a_persisted_session_starts_with_a_queued_job(db_session: DbSession,
                                                      app_database: str) -> None:
    """Written in the Session's own transaction (ADR 0034), so a call that was
    persisted at all is always answerable -- there is no window in which the
    client polls a Session with no job to report on."""
    _store()
    session_id = db_session.query(Session).one().session_id

    job = _job(db_session, session_id)

    assert (job.status, job.attempts, job.error_text) == ("queued", 0, None)


def test_the_job_says_running_while_the_model_is_being_asked(
    db_session: DbSession, app_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`running` has to be committed before the call, not after it: the LLM
    request is the slow part, and it is exactly the stretch the client is
    polling through. Observed from inside the stubbed model call."""
    _store()
    session_id = db_session.query(Session).one().session_id
    seen = []

    def observe(_messages):
        # A connection of its own: the worker's transaction is still open, so
        # only a committed transition is visible here.
        engine = db_session.get_bind()
        with engine.connect() as conn:
            seen.append(tuple(conn.exec_driver_sql(
                "SELECT status, attempts FROM analysis_job WHERE session_id = %s",
                (session_id,),
            ).one()))
        return _REPLY

    _stub_model(monkeypatch, observe)

    generate_feedback(session_id)

    assert seen == [("running", 1)]


def test_a_generated_wrapup_leaves_the_job_done(
    db_session: DbSession, app_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The transition the client waits for: `done` and the Feedback row are
    written in the same transaction, so the status can never promise a wrap-up
    that is not there."""
    _store()
    session_id = db_session.query(Session).one().session_id
    _stub_model(monkeypatch, _REPLY)

    generate_feedback(session_id)

    job = _job(db_session, session_id)
    assert (job.status, job.attempts, job.error_text) == ("done", 1, None)
    # The validated wrap-up, not the fallback: that one stores the raw model
    # text as the summary and no points at all.
    feedback = db_session.query(Feedback).filter_by(session_id=session_id).one()
    assert feedback.summary == _SUMMARY
    assert len(feedback.points) == 2


def test_a_failed_generation_is_recorded_with_its_error(
    db_session: DbSession, app_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`error_text` has no reader in the application; it is for whoever looks
    at the failed Session afterwards (ADR 0032), which is the whole reason the
    status is persisted rather than left in Redis."""
    _store()
    session_id = db_session.query(Session).one().session_id

    def fail(_messages):
        raise RuntimeError("gateway unreachable")

    _stub_model(monkeypatch, fail)

    with pytest.raises(RuntimeError):
        generate_feedback(session_id)

    job = _job(db_session, session_id)
    assert job.status == "failed"
    assert "gateway unreachable" in job.error_text


def test_a_job_that_was_never_queued_is_marked_failed(db_session: DbSession,
                                                      app_database: str) -> None:
    """Redis being unreachable at enqueue time is the one failure the live path
    knows for certain: no worker will ever see the job, so leaving the row at
    `queued` would describe a job that does not exist."""
    _store()
    session_id = db_session.query(Session).one().session_id

    persistence.mark_feedback_failed(session_id, "Error 111 connecting to redis:6379")

    job = _job(db_session, session_id)
    assert job.status == "failed"
    assert "redis" in job.error_text


def test_failing_a_job_that_is_not_there_is_survivable(db_session: DbSession,
                                                       app_database: str) -> None:
    """It runs while the live path is already handling a failure, so it must
    not add a second one -- the user is waiting on their transcript."""
    _store()
    session_id = db_session.query(Session).one().session_id
    db_session.query(AnalysisJob).delete()
    db_session.commit()

    persistence.mark_feedback_failed(session_id, "boom")  # must not raise


async def test_a_session_without_a_job_reads_as_failed(
    db_session: DbSession, api_client: httpx.AsyncClient
) -> None:
    """No row means nothing will ever generate a wrap-up, which is `failed`
    from the client's side rather than a fifth status for it to handle."""
    extern_id = _store()
    db_session.query(AnalysisJob).delete()
    db_session.commit()

    body = (await api_client.get(f"/api/sessions/{extern_id}")).json()

    assert body["status"] == "failed"


@pytest.mark.parametrize(
    ("age_s", "expected"),
    [(JOB_TIMEOUT_S + 60, "failed"), (5, "running")],
)
async def test_a_running_job_is_only_believed_within_its_timeout(
    db_session: DbSession, api_client: httpx.AsyncClient, age_s: int, expected: str
) -> None:
    """A worker killed mid-job leaves `running` behind for good -- nothing
    reconciles the row (ADR 0032). Past the timeout that bounds a job's run it
    is read as failed; inside it, a slow job is still a running one."""
    extern_id = _store()
    job = db_session.query(AnalysisJob).one()
    job.status = "running"
    job.updated_at = datetime.now(UTC) - timedelta(seconds=age_s)
    db_session.commit()

    body = (await api_client.get(f"/api/sessions/{extern_id}")).json()

    assert body["status"] == expected
