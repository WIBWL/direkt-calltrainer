"""Deleting a subject's stored trainings (ADR 0066).

The one place that removes user data, so that every entry point — the consent
withdrawal today, a "delete this training" button later — goes through the same
code rather than each growing its own idea of what belongs to a person.

It is deliberately small, because the schema already does the work. Everything
a Session owns hangs off it with `ON DELETE CASCADE` and `passive_deletes=True`
(ADR 0026/0052), so deleting the Session rows removes their Turns, Measurements,
Findings, Feedback, FeedbackPoints and AnalysisJobs with them, by raw SQL as
well as through the ORM — which `tests/test_cascade_delete.py` already pins
down. Reference data (Persona, Scenario, Language, MetricType) is untouched by
construction: those foreign keys carry no `ondelete` at all. The one Scenario
that belongs to a Session — the follow-up drafted from its feedback (ADR 0069)
— is deactivated rather than deleted, for the reason `retire_follow_ups` gives.

One exception: a reverse Scenario (ADR 0070) is content about the subject's own
call rather than reference data — it carries a briefing written from that call's
wrap-up — so it is removed rather than left standing. Two of the three paths do
that: the withdrawal (`delete_subject_sessions`) and the retention sweep, which
reaches it through `reverses_of` plus `delete_unreferenced_reverses`. Deleting a
*single* training deliberately does not, and the profile screen says so: there a
person is deciding about that one training and can remove the reverse herself,
where the other two paths run with nobody deciding anything.

What this module does *not* do is claim to be a complete erasure. Two limits
are known and named rather than papered over: backups are not reached (there is
no surgical delete from a snapshot), and the transcript that STT logged in
plaintext is not reached either. Both are recorded in ADR 0066.
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session as DbSession

from backend.db import models as db_models

logger = logging.getLogger(__name__)


def retire_follow_ups(db: DbSession, sessions: list[db_models.Session]) -> None:
    """Deactivate the follow-up Scenarios drafted from these Sessions (ADR 0069).

    Deactivated rather than deleted, and this is the one place that decides it:
    a later Session may have been played on such a Scenario, `session.scenario_id`
    is NOT NULL and carries no `ondelete` (ADR 0026), and that training has to
    stay readable. `active = False` is what reference rows retired from the seed
    already use — it takes the row out of the library and leaves everything that
    points at it intact.

    Called before the Sessions go, from every path that removes one: the
    withdrawal and the single delete below, and the retention sweep
    (`backend/retention.py`). The column's `ON DELETE SET NULL` then clears the
    provenance, so this is not a place a raw-SQL delete can leave inconsistent —
    only one where it would leave the Scenario on offer.
    """
    session_ids = [session.session_id for session in sessions]
    if not session_ids:
        return
    db.query(db_models.Scenario).filter(
        db_models.Scenario.derived_from_session_id.in_(session_ids)
    ).update({"active": False}, synchronize_session=False)


def reverses_of(db: DbSession, sessions: list[db_models.Session]) -> list[int]:
    """The reverse Scenarios replaying these Sessions, by primary key.

    Has to be read *before* the Sessions go: `origin_session_id` carries
    `ON DELETE SET NULL` (ADR 0070), so the moment they are deleted nothing
    connects the two any more and the reverse looks like any other row.

    Split from the delete below because the retention sweep needs the two halves
    on either side of its own delete, and because what can go is not decided
    here — see `delete_unreferenced_reverses`.
    """
    session_ids = [session.session_id for session in sessions]
    if not session_ids:
        return []
    return [
        row.scenario_id
        for row in db.query(db_models.Scenario)
        .filter(db_models.Scenario.origin_session_id.in_(session_ids))
        .all()
    ]


def delete_unreferenced_reverses(db: DbSession, scenario_ids: list[int]) -> int:
    """Delete those of `scenario_ids` no Session points at any more.

    The retention counterpart of `_delete_reverses` (ADR 0070's addendum). The
    withdrawal can delete every reverse outright because it has just removed all
    of that subject's Sessions; the sweep removes only the *expired* ones, so a
    reverse played more recently than its origin still has a live
    `session.scenario_id` pointing at it — and that column carries no `ondelete`
    at all (ADR 0052), so deleting the row would be refused and would take the
    whole sweep down with it.

    Those rows are left for a later run rather than special-cased: once the
    younger Session expires too, nothing references the reverse and it goes. A
    reverse somebody keeps playing therefore outlives the period, which is the
    right answer -- it is in use, not merely lying around.

    Hard-deleted, not deactivated, for the reason `_delete_reverses` gives: the
    briefing is written from that person's own wrap-up, and deactivation keeps
    the text.
    """
    if not scenario_ids:
        return 0
    still_played = {
        scenario_id
        for (scenario_id,) in db.query(db_models.Session.scenario_id)
        .filter(db_models.Session.scenario_id.in_(scenario_ids))
        .distinct()
    }
    doomed = [
        db.get(db_models.Scenario, scenario_id)
        for scenario_id in scenario_ids
        if scenario_id not in still_played
    ]
    for scenario in doomed:
        if scenario is not None:
            db.delete(scenario)
    db.flush()
    if doomed:
        logger.info("Deleted %d expired reverse scenario(s)", len(doomed))
    return len(doomed)


def delete_subject_sessions(db: DbSession, subject_id: str) -> int:
    """Delete every stored Session of one subject. Returns how many went.

    Idempotent: a second call finds nothing and returns 0. That matters more
    than it looks — a withdrawal that is retried after a timeout must not
    become an error, and a user who clicks twice must not see a failure for
    work that already succeeded.

    Loaded and deleted through the ORM rather than issued as one bulk
    `DELETE ... WHERE subject_id = ...`. A bulk delete bypasses the ORM's
    cascade handling and would lean entirely on the database's, which happens
    to be correct here — but the two are declared as a pair on purpose
    (ADR 0026), and quietly relying on only one of them is how the other stops
    being maintained.
    """
    sessions = db.query(db_models.Session).filter_by(subject_id=subject_id).all()
    retire_follow_ups(db, sessions)
    for session in sessions:
        db.delete(session)
    # Flushed here rather than left to the caller's commit, so a caller that
    # goes on to write in the same transaction (the withdrawal does) cannot
    # observe rows this call has logically already removed.
    db.flush()
    _delete_reverses(db, subject_id)
    logger.info("Deleted %d stored session(s) for the subject", len(sessions))
    return len(sessions)


def _delete_reverses(db: DbSession, subject_id: str) -> None:
    """Remove the subject's reverse Scenarios (ADR 0070).

    The one place where a withdrawal reaches beyond the `session` table, and
    deliberately: a reverse carries a briefing written from that person's own
    wrap-up, so leaving the row would leave a reading of feedback whose
    conversation has just been deleted. An ordinary authored Scenario is not
    touched — it is the User's own work about a case, not a record of a call
    they had.

    After the Sessions, never before: a reverse Session points at its Scenario
    through `session.scenario_id`, which carries no `ondelete` at all
    (ADR 0052), so this delete would be refused while such a row still stood.

    Hard-deleted rather than deactivated, unlike every other Scenario retirement
    (ADR 0058): deactivation keeps the text, and the text is what has to go.
    """
    reverses = (
        db.query(db_models.Scenario)
        .filter_by(created_by=subject_id, reverse=True)
        .all()
    )
    for scenario in reverses:
        db.delete(scenario)
    db.flush()
    if reverses:
        logger.info("Deleted %d reverse scenario(s) for the subject", len(reverses))


def delete_session(db: DbSession, subject_id: str, extern_id: uuid.UUID) -> bool:
    """Delete one of the subject's Sessions. True if there was one to delete.

    Ownership is part of the query, not a check on its result — the same shape
    the history uses (ADR 0064), and for the same reason: a filter cannot be
    forgotten on one path the way a comparison can, and there is no version of
    this call that should ever reach somebody else's row.

    Returns False rather than raising for an id that is absent *or* not the
    caller's. The two are deliberately indistinguishable (ADR 0031/0050), and
    the route turns this into the same 404 a stale link gets — telling the
    caller that an id exists but is not theirs is exactly what the unguessable
    id is there to withhold.
    """
    session = (
        db.query(db_models.Session)
        .filter_by(extern_id=extern_id, subject_id=subject_id)
        .one_or_none()
    )
    if session is None:
        return False
    retire_follow_ups(db, [session])
    db.delete(session)
    db.flush()
    logger.info("Deleted one stored session")
    return True
