"""The AnalysisJob row behind the post-call poll (ADR 0032, F-09, F-10).

Written `queued` with the Session (ADR 0034), moved by the worker, served as
`status` (ADR 0050). A missing transition fails quietly: the client gives up and
shows a failure that did not happen. Needs Postgres; skips without."""

# pylint: disable=duplicate-code
# Fixture data is repeated per test module on purpose: a test carrying its own
# Turns shows what it ran against when it fails, and sharing them would let a
# change made for one test quietly alter another.


import json
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy.orm import Session as DbSession

from backend.clients import llm
from backend.db.models import AnalysisJob, Feedback, Session
from backend.feedback import jobs
from backend.feedback.generator import generate_feedback
from backend.feedback.jobs import JOB_TIMEOUT_S
from backend.session.models import Turn
from tests.conftest import persist

# `app_database` is taken by several tests only to activate the fixture.
# pylint: disable=unused-argument

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
    """Replace the wrap-up's model call with `reply` (text, or a callable).

    The keyword-only arguments mirror `llm.complete`'s real signature.
    """
    async def complete(messages: list[dict[str, str]], *,
                       max_tokens: int | None = None, think: bool = False) -> str:
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

    assert seen[0] == ("running", 1)
    # Whatever follows is the follow-up Scenario's own call (ADR 0069), and it
    # is asked only once the wrap-up job is closed.
    assert set(seen[1:]) <= {("done", 1)}


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


@pytest.mark.parametrize(
    "goal, expected",
    [
        ("closing", "closing"),
        # Not in the catalogue: the model reached for a sixteenth key.
        ("small_talk", None),
        # In the catalogue, but about the training habit rather than the call.
        ("training_regularity", None),
        ("", None),
    ],
    ids=["known", "invented", "habit goal", "none offered"],
)
def test_a_points_goal_is_resolved_against_the_catalogue(
    db_session: DbSession, app_database: str, monkeypatch: pytest.MonkeyPatch,
    goal: str, expected: str | None,
) -> None:
    """A bad focus-goal tag becomes NULL, never an error.

    Losing the wrap-up over a label is the wrong trade, but a wrong key would count a
    weakness the person does not have. The two habit goals are refused here as well
    as in the prompt, since a single call cannot show them."""
    _store()
    session_id = db_session.query(Session).one().session_id
    _stub_model(monkeypatch, json.dumps({
        "summary": _SUMMARY,
        "strengths": [],
        "improvements": [{"text": "Mehr Pausen lassen.", "goal": goal}],
    }))

    generate_feedback(session_id)

    point = db_session.query(Feedback).filter_by(session_id=session_id).one().points[0]
    assert (point.focus_goal.key if point.focus_goal else None) == expected


def test_a_wrapup_written_before_the_tag_leaves_its_points_untagged(
    db_session: DbSession, app_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A model answer with no `goal` key at all, which is what every stored
    wrap-up from before this feature looks like. The point is kept and simply
    carries no tag; the dashboard leaves it out of its counts rather than
    filing it under a goal nobody chose."""
    _store()
    session_id = db_session.query(Session).one().session_id
    _stub_model(monkeypatch, _REPLY)

    generate_feedback(session_id)

    points = db_session.query(Feedback).filter_by(session_id=session_id).one().points
    assert len(points) == 2
    assert all(point.focus_goal_id is None for point in points)


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

    jobs.mark_failed(session_id, "Error 111 connecting to redis:6379")

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

    jobs.mark_failed(session_id, "boom")  # must not raise


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


def test_a_wrapup_that_cannot_be_stored_fails_the_job(
    db_session: DbSession, app_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Generation and storage are two steps and either can fail. A boundary
    drawn around the model call alone would let a storage failure escape with
    the row still at `running`, which is the state the client keeps polling."""
    _store()
    session_id = db_session.query(Session).one().session_id
    _stub_model(monkeypatch, _REPLY)

    def fail_store(_db, _session_id, _wrapup, _turn_ids):
        raise RuntimeError("feedback_point insert failed")

    monkeypatch.setattr("backend.feedback.generator._store", fail_store)

    # Re-raised on purpose: RQ has to see the job fail, or it counts as done.
    with pytest.raises(RuntimeError, match="feedback_point insert failed"):
        generate_feedback(session_id)

    job = _job(db_session, session_id)
    assert job.status == "failed"
    assert "feedback_point insert failed" in job.error_text


def test_a_late_failure_does_not_overwrite_a_finished_job(
    db_session: DbSession, app_database: str
) -> None:
    """`jobs.mark_failed` writes from outside the process running the job, so by
    the time it commits the wrap-up may already be on the user's screen. Taking
    a result away from them is worse than a row that is briefly out of date."""
    _store()
    session_id = db_session.query(Session).one().session_id
    job = _job(db_session, session_id)
    job.status = "done"
    db_session.commit()

    jobs.mark_failed(session_id, "late failure")

    job = _job(db_session, session_id)
    assert (job.status, job.error_text) == ("done", None)


def test_a_session_that_was_never_written_leaves_no_job_behind(
    db_session: DbSession, app_database: str
) -> None:
    """The worker's writer creates the row where it finds none, so a job id
    pointing at nothing has to stop before it rather than leave a dangling
    row nothing will ever read."""
    with pytest.raises(LookupError):
        generate_feedback(4_711)

    assert db_session.query(AnalysisJob).filter_by(session_id=4_711).count() == 0


def test_a_call_with_nothing_in_it_is_summarised_without_the_model(
    db_session: DbSession, app_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A training broken off before a word was said.

    Nothing is asked of the model: a 4B model answers O5 in English on a German
    screen, so the sentence is written here in the Session's language.
    """
    asked: list = []
    _stub_model(monkeypatch, lambda messages: asked.append(messages) or _REPLY)
    persist(turns=[])
    session_id = db_session.query(Session).one().session_id

    generate_feedback(session_id)

    db_session.expire_all()
    feedback = db_session.query(Feedback).one()
    assert not asked, "an empty call costs no model call"
    assert feedback.summary.startswith("In diesem Training wurde nicht gesprochen")
    assert feedback.points == []
    assert feedback.phase_language is None
    assert _job(db_session, session_id).status == "done"


# --- Whether a job may still be working (no database) ----------------------

def _in_memory_job(status: str, age_s: float | None = 5, naive: bool = False) -> AnalysisJob:
    """One job row, in memory. `age_s` None leaves it without a timestamp."""
    if age_s is None:
        return AnalysisJob(status=status, updated_at=None)
    moved = datetime.now(UTC) - timedelta(seconds=age_s)
    return AnalysisJob(status=status, updated_at=moved.replace(tzinfo=None) if naive else moved)


@pytest.mark.parametrize("status", ["done", "failed"])
def test_a_finished_job_is_not_working(status: str) -> None:
    """Terminal either way: nothing will move it again."""
    assert not jobs.is_live(_in_memory_job(status), include_queued=True)
    assert not jobs.is_live(_in_memory_job(status), include_queued=False)


def test_a_queued_job_is_working_only_for_a_caller_that_asked_about_queued() -> None:
    """The one thing the two readers differ on, as a parameter rather than as a
    second copy: a reader showing a status must not call a waiting job
    abandoned, and a writer about to queue a second one must not call it idle."""
    assert jobs.is_live(_in_memory_job("queued"), include_queued=True)
    assert not jobs.is_live(_in_memory_job("queued"), include_queued=False)


@pytest.mark.parametrize(
    ("age_s", "live"), [(5, True), (JOB_TIMEOUT_S - 1, True), (JOB_TIMEOUT_S + 60, False)]
)
def test_a_running_job_is_believed_only_inside_the_window(age_s: float, live: bool) -> None:
    """Past the timeout that bounds a job's run, the worker holding it is gone."""
    assert jobs.is_live(_in_memory_job("running", age_s), include_queued=False) is live


def test_a_naive_timestamp_is_read_as_utc_rather_than_raising() -> None:
    """Comparing an aware and a naive datetime raises, and this is read while
    serving a Session: a 500 here would cost the User a wrap-up that exists.
    The read side coerced, the script would have raised -- one of the two
    divergences that came of answering this question twice."""
    assert jobs.is_live(_in_memory_job("running", 5, naive=True), include_queued=False)
    assert not jobs.is_live(_in_memory_job("running", JOB_TIMEOUT_S + 60, naive=True), include_queued=False)


def test_a_job_without_a_timestamp_is_not_working() -> None:
    """Nothing can be said about its age. The script guarded against this and
    the read side did not; the guard is now on both."""
    assert not jobs.is_live(_in_memory_job("running", None), include_queued=True)


# --- Asking for a wrap-up again (POST /api/sessions/{extern_id}/feedback) ----
#
# A failed wrap-up can be regenerated from the stored Transcript and
# Measurements (ADR 0048/0049).


def _queue_spy(monkeypatch, fail: bool = False) -> list[int]:
    """Replace the enqueue so no Redis is needed; returns what it was given."""
    from backend.feedback import queue  # pylint: disable=import-outside-toplevel

    taken: list[int] = []

    def enqueue(session_id: int) -> None:
        if fail:
            raise ConnectionError("no redis")
        taken.append(session_id)

    monkeypatch.setattr(queue, "enqueue_feedback", enqueue)
    return taken


async def test_a_failed_wrapup_can_be_asked_for_again(
    api_client: httpx.AsyncClient, db_session: DbSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The point of the route: the Session is put back on the queue and its row
    says so, so the screen stops showing a failure and starts polling again."""
    extern_id = _store()
    session_id = db_session.query(Session).one().session_id
    jobs.mark_failed(session_id, "gateway down")
    taken = _queue_spy(monkeypatch)

    response = await api_client.post(f"/api/sessions/{extern_id}/feedback")

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert taken == [session_id]
    assert _job(db_session, session_id).status == "queued"


async def test_a_session_that_already_has_a_wrapup_is_refused(
    api_client: httpx.AsyncClient, db_session: DbSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`feedback.session_id` is UNIQUE, so a second job would write nothing and
    be recorded as failed for a Session the User can already read."""
    extern_id = _store()
    session_id = db_session.query(Session).one().session_id
    # `created_at` has a Python-side default only (no server_default), and a
    # row built by hand here has to name it — see CLAUDE.md on column defaults.
    db_session.add(
        Feedback(session_id=session_id, summary=_SUMMARY, created_at=datetime.now(UTC))
    )
    db_session.commit()
    taken = _queue_spy(monkeypatch)

    response = await api_client.post(f"/api/sessions/{extern_id}/feedback")

    assert response.status_code == 409
    assert not taken


async def test_a_job_that_may_still_be_working_is_refused(
    api_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Session is written with a queued job (ADR 0034). Two jobs would race
    for the same row, which is the defect `requeue_feedback.py` was corrected
    for -- and this route asks the same question it does."""
    extern_id = _store()
    taken = _queue_spy(monkeypatch)

    response = await api_client.post(f"/api/sessions/{extern_id}/feedback")

    assert response.status_code == 409
    assert not taken


async def test_someone_elses_session_is_a_404_like_everywhere(
    api_client: httpx.AsyncClient, db_session: DbSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Absent and not-yours are the same answer (ADR 0031/0050): a 403 would
    confirm the id exists, which is what the unguessable id withholds."""
    extern_id = _store()
    session = db_session.query(Session).one()
    session.subject_id = "somebody-else"
    db_session.commit()
    taken = _queue_spy(monkeypatch)

    assert (await api_client.post(f"/api/sessions/{extern_id}/feedback")).status_code == 404
    assert (await api_client.post(f"/api/sessions/{uuid.uuid4()}/feedback")).status_code == 404
    assert not taken


async def test_an_unreachable_queue_leaves_the_row_where_it_was(
    api_client: httpx.AsyncClient, db_session: DbSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Moving the row to `queued` with nothing behind it is the exact state
    `requeue_feedback.py` exists to repair -- the screen would show a spinner
    that never ends instead of the failure it already showed."""
    extern_id = _store()
    session_id = db_session.query(Session).one().session_id
    jobs.mark_failed(session_id, "gateway down")
    _queue_spy(monkeypatch, fail=True)

    response = await api_client.post(f"/api/sessions/{extern_id}/feedback")

    assert response.status_code == 503
    assert _job(db_session, session_id).status == "failed"
