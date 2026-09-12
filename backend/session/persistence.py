"""Writing a finished Session to the database (ADR 0034).

One transaction, once, after the call has ended -- never from inside the live
turn loop, which must not be able to fail because of the database.

This is the seam between the in-memory Session and the schema: it takes the two
readings of a finished Session that backend/feedback/calls.py produces -- the
utterances on their timeline, and the call folded into the facts its statistics
come from -- and writes them as rows.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session as DbSession

# Imported as a module, not by name: `db.Session`/`db.Turn` keep the schema's
# entities visibly distinct from the identically named in-memory ones.
from backend.db import models as db_models
from backend.db.session import session_scope
from backend.feedback import interruptions, metrics
from backend.feedback.calls import Conversation, conversation, utterances
from backend.personas import Persona
from backend.scenarios import Scenario
from backend.session.models import Turn

logger = logging.getLogger(__name__)

# How a Session ended, in the wire protocol's vocabulary -> in the schema's.
_STATUS = {
    "user": db_models.STATUS_COMPLETED,
    "completed": db_models.STATUS_COMPLETED,
    "error": db_models.STATUS_ABORTED,
}


def persist_session(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    extern_id: uuid.UUID,
    subject_id: str,
    persona: Persona,
    scenario: Scenario,
    turns: Sequence[Turn],
    started_at: datetime,
    reason: str,
) -> int:
    """Write the Session, its Turns and its measurements. Returns session_id.

    `subject_id` is the Keycloak `sub` from the handshake (ADR 0009): the
    Session belongs to the account that placed the call, not to a placeholder
    (ADR 0031).

    Synchronous by design: the caller dispatches it off the event loop once the
    call is over (ADR 0034), so nothing here has to be async-aware.
    """
    with session_scope() as db:
        session = db_models.Session(
            extern_id=extern_id,
            subject_id=subject_id,
            persona=_reference(db, db_models.Persona, persona.id),
            scenario=_reference(db, db_models.Scenario, scenario.id),
            language_code=persona.language_id,
            status=_STATUS.get(reason, db_models.STATUS_ABORTED),
            started_at=started_at,
            ended_at=datetime.now(UTC),
        )
        session.turns = [
            db_models.Turn(
                speaker=spoken.speaker,
                seq_index=index,
                start_offset_ms=spoken.offset_ms,
                duration_ms=spoken.duration_ms,
                transcript=spoken.text,
                interrupted=spoken.interrupted,
                unheard_text=spoken.unheard or None,
                # The raw facts of this utterance, kept because the audio they
                # were measured from is discarded when the call ends (ADR 0048)
                # while which stretch of the call was demanding is decided
                # afterwards, by the wrap-up (ADR 0081). NULL on a Persona row.
                acoustics_json=spoken.acoustics.as_json() if spoken.acoustics else None,
            )
            for index, spoken in enumerate(utterances(turns))
        ]
        _write_analysis(
            db, session, conversation(turns, persona.language_id, scenario.reverse)
        )
        # The wrap-up itself is generated asynchronously (ADR 0018/0019); this
        # row is what makes its outcome queryable afterwards (ADR 0032).
        session.jobs = [db_models.AnalysisJob(
            kind=db_models.JOB_KIND_FEEDBACK,
            status=db_models.JOB_QUEUED,
            attempts=0,
            updated_at=datetime.now(UTC),
        )]
        db.add(session)
        db.flush()
        logger.info("Session persisted: id=%d turns=%d measurements=%d",
                    session.session_id, len(session.turns), len(session.measurements))
        return session.session_id


def _write_analysis(
    db: DbSession, session: db_models.Session, call: Conversation
) -> None:
    """Attach the Session's Measurement and Finding rows.

    A metric the seed does not know is dropped rather than written against a
    guessed reference row -- provision.py seeds the inventory from the same
    METRICS tuple, so that can only happen against a database behind the code.

    Findings are written for one thing only, and the distinction is what makes
    it allowable: a hard interruption is an *event that occurred at a moment*,
    not a value judged against a threshold. ADR 0051 keeps the table empty for
    the second kind, because marking a figure as remarkable takes a norm nobody
    measured. Nothing of that sort is written here -- an overlap either happened
    or it did not, and the row says when.
    """
    metric_ids = {m.key: m.metric_type_id for m in db.query(db_models.MetricType).all()}
    session.measurements = [
        db_models.Measurement(
            metric_type_id=metric_ids[m.key],
            value=Decimal(f"{m.value:.4f}"),
            detail_json=m.detail,
        )
        for m in metrics.measure(call)
        if m.key in metric_ids
    ]
    session.findings = [
        db_models.Finding(
            metric_type_id=metric_ids.get(interruptions.COUNT_KEY),
            category=interruptions.FINDING_CATEGORY,
            offset_ms=event.offset_ms,
            description=interruptions.finding_description(event),
        )
        for event in interruptions.classify(call.timeline).hard
    ]


def _reference(db: DbSession, model: type, extern_id: str):
    """The Persona / Scenario row a Session points at, by its `extern_id`.

    That is what the value object carries as `.id` since ADR 0058 (an authored
    row has no `key` slug). Assigned through the relationship rather than the
    foreign key, so the primary key never has to be named here -- only Persona
    and Scenario go through this, the Feedback tables are attached directly, by
    id. `active` is not checked -- a Session may reference a since-retired row,
    same as before.
    """
    try:
        ref = uuid.UUID(str(extern_id))
    except (ValueError, TypeError) as e:
        raise LookupError(f"{model.__name__} {extern_id!r} is not a valid id") from e
    row = db.query(model).filter_by(extern_id=ref).one_or_none()
    if row is None:
        raise LookupError(f"{model.__name__} {extern_id!r} is not seeded")
    return row
