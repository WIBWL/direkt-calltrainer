"""Writing a finished Session to the database (ADR 0034).

One transaction, once, after the call has ended -- never from inside the live
turn loop, which must not be able to fail because of the database.

This is the seam between the in-memory Session and the schema: it takes the two
readings of a finished Session that backend/session/models.py produces -- the
utterances on their timeline, and the call folded into the facts its statistics
come from -- and writes them as rows.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session as DbSession

# Imported as a module, not by name: `db.Session`/`db.Turn` keep the schema's
# entities visibly distinct from the identically named in-memory ones.
from backend.db import models as db_models
from backend.db.session import session_scope
from backend.feedback import metrics
from backend.personas import Persona
from backend.scenarios import Scenario
from backend.session.models import Turn, conversation, utterances

logger = logging.getLogger(__name__)

# How a Session ended, in the wire protocol's vocabulary -> in the schema's.
_STATUS = {
    "user": db_models.STATUS_COMPLETED,
    "completed": db_models.STATUS_COMPLETED,
    "error": db_models.STATUS_ABORTED,
}


def persist_session(
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
            ended_at=datetime.now(),
        )
        session.turns = [
            db_models.Turn(
                speaker=spoken.speaker,
                seq_index=index,
                start_offset_ms=spoken.offset_ms,
                duration_ms=spoken.duration_ms,
                transcript=spoken.text,
            )
            for index, spoken in enumerate(utterances(turns))
        ]
        _write_analysis(db, session, conversation(turns))
        # The wrap-up itself is generated asynchronously (ADR 0018/0019); this
        # row is what makes its outcome queryable afterwards (ADR 0032).
        session.jobs = [db_models.AnalysisJob(
            kind="feedback", status="queued", attempts=0, updated_at=datetime.now(),
        )]
        db.add(session)
        db.flush()
        logger.info("Session persisted: id=%d turns=%d measurements=%d",
                    session.session_id, len(session.turns), len(session.measurements))
        return session.session_id


def _write_analysis(
    db: DbSession, session: db_models.Session, call: metrics.Conversation
) -> None:
    """Attach the Session's Measurement rows.

    No `Finding` rows are written: marking a value as remarkable takes a norm to
    compare it against, and none of these metrics has one that was measured
    rather than guessed (ADR 0051). The table waits for pilot data.

    A metric the seed does not know is dropped rather than written against a
    guessed reference row -- provision.py seeds the inventory from the same
    METRICS tuple, so that can only happen against a database behind the code.
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


def _reference(db: DbSession, model: type, key: str):
    """A seeded reference row, by its natural key.

    Assigned through the relationship rather than the foreign key, so the
    primary key never has to be named here. Only Persona and Scenario go
    through this -- the Feedback tables are attached directly, by id.
    """
    row = db.query(model).filter_by(key=key).one_or_none()
    if row is None:
        raise LookupError(f"{model.__name__} {key!r} is not seeded")
    return row
