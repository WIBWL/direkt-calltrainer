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
_STATUS = {"user": "beendet", "completed": "beendet", "error": "abgebrochen"}


def persist_session(
    oeffentliche_id: uuid.UUID,
    subject_id: str,
    persona: Persona,
    scenario: Scenario,
    turns: Sequence[Turn],
    gestartet_am: datetime,
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
            oeffentliche_id=oeffentliche_id,
            subject_id=subject_id,
            persona=_reference(db, db_models.Persona, persona.id),
            szenario=_reference(db, db_models.Szenario, scenario.id),
            sprache_code=persona.language_id,
            status=_STATUS.get(reason, "abgebrochen"),
            gestartet_am=gestartet_am,
            beendet_am=datetime.now(),
        )
        session.turns = [
            db_models.Turn(
                sprecher=spoken.sprecher,
                seq_index=index,
                start_offset_ms=spoken.offset_ms,
                dauer_ms=spoken.dauer_ms,
                transkript=spoken.text,
            )
            for index, spoken in enumerate(utterances(turns))
        ]
        _write_analysis(db, session, conversation(turns))
        # The wrap-up itself is generated asynchronously (ADR 0018/0019); this
        # row is what makes its outcome queryable afterwards (ADR 0032).
        session.jobs = [db_models.AnalysisJob(
            art="feedback", status="queued", versuche=0, aktualisiert_am=datetime.now(),
        )]
        db.add(session)
        db.flush()
        logger.info("Session persisted: id=%d turns=%d messungen=%d",
                    session.session_id, len(session.turns), len(session.messungen))
        return session.session_id


def _write_analysis(
    db: DbSession, session: db_models.Session, call: metrics.Conversation
) -> None:
    """Attach the Session's Messung rows.

    No `Befund` rows are written: marking a value as remarkable takes a norm to
    compare it against, and none of these metrics has one that was measured
    rather than guessed (ADR 0051). The table waits for pilot data.

    A metric the seed does not know is dropped rather than written against a
    guessed reference row -- provision.py seeds the inventory from the same
    METRICS tuple, so that can only happen against a database behind the code.
    """
    metrik_ids = {m.schluessel: m.metrik_typ_id for m in db.query(db_models.MetrikTyp).all()}
    session.messungen = [
        db_models.Messung(
            metrik_typ_id=metrik_ids[m.schluessel],
            wert=Decimal(f"{m.wert:.4f}"),
            detail_json=m.detail,
        )
        for m in metrics.measure(call)
        if m.schluessel in metrik_ids
    ]


def _reference(db: DbSession, model: type, schluessel: str):
    """A seeded reference row, by its natural key.

    Assigned through the relationship rather than the foreign key, so the
    primary key never has to be named here.
    """
    row = db.query(model).filter_by(schluessel=schluessel).one_or_none()
    if row is None:
        raise LookupError(f"{model.__name__} {schluessel!r} is not seeded")
    return row
