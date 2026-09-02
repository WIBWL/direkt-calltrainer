"""
Persistence schema of the Calltrainer (ADR 0026).

Single source of truth: both the Alembic migrations and the ER diagram are
derived from these classes, so neither can drift from the schema.

Conventions: one concept is one class is one table; table and column names are
English and follow the domain glossary in CONTEXT.md, so a term means the same
thing in the schema as it does in the code around it. German remains only in
user-facing content and in the documentation.

Deletes are declared twice on purpose: `ondelete` on the foreign key so the
database enforces them even for raw SQL, and `passive_deletes=True` on the
matching relationship so the ORM lets it do the work instead of issuing one
statement per child row. Ownership edges cascade; the optional back-references
from a FeedbackPoint are set to NULL, because the point still says something
without the Turn it pointed at. Foreign keys into the reference tables carry no
ondelete at all — a Persona with stored Sessions must not be deletable.

Every foreign-key column is indexed. Postgres indexes the referenced primary
key but never the referencing side, so without this a delete of one Session
sequentially scans every child table looking for rows to reject — exactly the
delete path ADR 0034 promises. It is the same default Django and Rails apply,
and the write cost is irrelevant at this volume.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base

# Session.status. The row is written once, after the Session has ended
# (ADR 0034), so there is no "running": a Session either finished normally or
# was cut short by a pipeline failure (ADR 0016).
STATUS_COMPLETED = "completed"
STATUS_ABORTED = "aborted"
SESSION_STATUSES = (STATUS_COMPLETED, STATUS_ABORTED)

# Turn.speaker. One row per utterance, so each row names exactly one speaker;
# backend/session/models.py's utterances() is what produces them.
SPEAKER_USER = "user"
SPEAKER_PERSONA = "persona"
SPEAKERS = (SPEAKER_USER, SPEAKER_PERSONA)

# FeedbackPoint.kind (F-10): what the point is saying about the Session.
POINT_STRENGTH = "strength"
POINT_IMPROVEMENT = "improvement"
POINT_KINDS = (POINT_STRENGTH, POINT_IMPROVEMENT)

# AnalysisJob vocabulary (ADR 0032). Kept here next to the schema, because the
# CHECK constraints below are what actually enforce them.
JOB_KINDS = ("analysis", "feedback")
JOB_STATUSES = ("queued", "running", "done", "failed")


def _one_of(column: str, values: tuple[str, ...]) -> CheckConstraint:
    """A CHECK restricting `column` to `values`.

    Plain columns with a CHECK rather than a Postgres ENUM type: adding a value
    later is a one-line constraint swap instead of an ALTER TYPE that cannot run
    inside a transaction.
    """
    allowed = ", ".join(f"'{v}'" for v in values)
    return CheckConstraint(f"{column} IN ({allowed})", name=f"{column}_valid")


class Persona(Base):
    """The simulated conversation partner. This table — not `backend/personas.py`
    — is the source of truth (ADR 0041); that module only seeds it, and ADR 0024
    has Users authoring their own Personas, which have to live here.

    A Persona has exactly one Language and one voice per TTS backend (ADR 0043),
    so all three are attributes here rather than something a User picks per
    Session.
    """

    __tablename__ = "persona"
    persona_id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(60), unique=True)  # e.g. thomas-brandt-ceo
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(120))
    traits: Mapped[str] = mapped_column(String(120))
    behavior: Mapped[str] = mapped_column(Text)
    training_goal: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(40))
    language_code: Mapped[str] = mapped_column(ForeignKey("language.code"), index=True)
    # The voice on the DiReKT fallback backend.
    tts_voice: Mapped[str] = mapped_column(String(60))
    # Only used when TTS runs on KugelAudio (ADR 0040), hence nullable.
    kugelaudio_voice_id: Mapped[int | None] = mapped_column(Integer)
    # Retired Personas are deactivated, never deleted: Session rows reference
    # them, and a past Session has to stay readable.
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    language: Mapped["Language"] = relationship(back_populates="personas")
    objections: Mapped[list["PersonaObjection"]] = relationship(
        back_populates="persona",
        order_by="PersonaObjection.position",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    sessions: Mapped[list["Session"]] = relationship(back_populates="persona")


class PersonaObjection(Base):
    """A typical objection of a Persona, kept as ordered rows rather than as a
    repeating group inside the persona row (ADR 0026)."""

    __tablename__ = "persona_objection"
    objection_id: Mapped[int] = mapped_column(primary_key=True)
    persona_id: Mapped[int] = mapped_column(
        ForeignKey("persona.persona_id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)

    persona: Mapped["Persona"] = relationship(back_populates="objections")


class Scenario(Base):
    """The situational context of a Session. Like Persona, this table is the
    source of truth and `backend/scenarios.py` only seeds it (ADR 0041)."""

    __tablename__ = "scenario"
    scenario_id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(60), unique=True)  # e.g. cold-call-followup
    # Not "type": that shadows the builtin wherever a row is unpacked.
    scenario_type: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    sessions: Mapped[list["Session"]] = relationship(back_populates="scenario")


class Language(Base):
    """The language a Session is conducted in. A closed code list, never
    deactivated: a Session keeps pointing at the code it ran in."""

    __tablename__ = "language"
    code: Mapped[str] = mapped_column(String(8), primary_key=True)
    name: Mapped[str] = mapped_column(String(60))

    personas: Mapped[list["Persona"]] = relationship(back_populates="language")
    sessions: Mapped[list["Session"]] = relationship(back_populates="language")


class MetricType(Base):
    """One measurable dimension of speaking behaviour, e.g. speaking rate.

    The inventory is owned by backend/feedback/metrics.py, which also seeds this
    table, so the metric list and the analysis cannot drift apart (ADR 0051).
    """

    __tablename__ = "metric_type"
    metric_type_id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(60), unique=True)  # e.g. speaking_rate
    name: Mapped[str] = mapped_column(String(120))
    unit: Mapped[str | None] = mapped_column(String(40))
    feature_id: Mapped[str | None] = mapped_column(String(10))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    measurements: Mapped[list["Measurement"]] = relationship(back_populates="metric_type")
    findings: Mapped[list["Finding"]] = relationship(back_populates="metric_type")
    feedback_points: Mapped[list["FeedbackPoint"]] = relationship(
        back_populates="metric_type"
    )


class Session(Base):
    """One simulated conversation. Written once, after it has ended (ADR 0034);
    a Session that the client abandoned mid-call never reaches this table."""

    __tablename__ = "session"
    __table_args__ = (_one_of("status", SESSION_STATUSES),)

    session_id: Mapped[int] = mapped_column(primary_key=True)
    # The id the client sees and later names the Session by (ADR 0050). Random
    # rather than the primary key: the wire never exposes a guessable sequence
    # number, and being unguessable is what keeps one user's Session from
    # another's. Defaulted so a caller without one still gets a valid id; the
    # live path passes its own, because session_ws.py hands the id to the
    # client when the socket opens, long before this row is written.
    extern_id: Mapped[uuid.UUID] = mapped_column(Uuid, unique=True, default=uuid.uuid4)
    # The caller's Keycloak "sub" claim (ADR 0009/0031), taken from the
    # WebSocket handshake.
    subject_id: Mapped[str] = mapped_column(String(64))
    persona_id: Mapped[int] = mapped_column(ForeignKey("persona.persona_id"), index=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("scenario.scenario_id"), index=True)
    # Deliberately duplicated from Persona.language_code rather than derived:
    # this records the Language the Session actually ran in, which must stay
    # correct even if the Persona is later edited (ADR 0024) or deactivated.
    language_code: Mapped[str] = mapped_column(ForeignKey("language.code"), index=True)
    # STATUS_COMPLETED or STATUS_ABORTED, see the constants above.
    status: Mapped[str] = mapped_column(String(20))
    # timezone=True throughout: the server's local time is not a property worth
    # storing, and a naive column silently loses the offset on read.
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    persona: Mapped["Persona"] = relationship(back_populates="sessions")
    scenario: Mapped["Scenario"] = relationship(back_populates="sessions")
    language: Mapped["Language"] = relationship(back_populates="sessions")
    turns: Mapped[list["Turn"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", passive_deletes=True
    )
    # Measurements and findings describe the whole call, not one utterance
    # (ADR 0051), so they hang off the Session rather than off a Turn.
    measurements: Mapped[list["Measurement"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", passive_deletes=True
    )
    findings: Mapped[list["Finding"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", passive_deletes=True
    )
    feedback: Mapped["Feedback | None"] = relationship(
        back_populates="session", cascade="all, delete-orphan", passive_deletes=True
    )
    jobs: Mapped[list["AnalysisJob"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", passive_deletes=True
    )


class Turn(Base):
    """One utterance by one speaker, in the order it was spoken.

    A Turn in the domain sense is an exchange (see CONTEXT.md), and that is how
    backend/session/models.py holds it in memory — but it is stored flattened,
    one row per speaker, because that is what makes the Gesprächsprotokoll
    timestamped: each row carries its own offset into the Session.
    `utterances()` is the single place that performs the flattening.
    """

    __tablename__ = "turn"
    __table_args__ = (
        _one_of("speaker", SPEAKERS),
        CheckConstraint("seq_index >= 0", name="seq_index_non_negative"),
        CheckConstraint("start_offset_ms >= 0", name="start_offset_non_negative"),
        # A negative duration would be a bug in the measurement, not a
        # measurement; NULL is the legitimate way to say "not measured".
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0", name="duration_non_negative"
        ),
    )

    turn_id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("session.session_id", ondelete="CASCADE"), index=True
    )
    # SPEAKER_USER or SPEAKER_PERSONA, see the constants above.
    speaker: Mapped[str] = mapped_column(String(10))
    seq_index: Mapped[int] = mapped_column(Integer)
    start_offset_ms: Mapped[int] = mapped_column(Integer)
    # NULL where an utterance has no measured end: a user Turn whose audio
    # could not be analysed, or a Persona line whose synthesis failed.
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    transcript: Mapped[str] = mapped_column(Text)

    session: Mapped["Session"] = relationship(back_populates="turns")
    feedback_points: Mapped[list["FeedbackPoint"]] = relationship(back_populates="turn")


class Measurement(Base):
    """One metric measured over the whole Session (ADR 0051).

    Session-level, not per Turn: none of the Kennzahlen (Redeanteil, Fragen,
    Sprechtempo, Wortanzahl, Reaktionszeit, Sprechpausen) is meaningful for a
    single utterance, and there is exactly one set of them per Session.
    """

    __tablename__ = "measurement"
    measurement_id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("session.session_id", ondelete="CASCADE"), index=True
    )
    metric_type_id: Mapped[int] = mapped_column(
        ForeignKey("metric_type.metric_type_id"), index=True
    )
    value: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    detail_json: Mapped[dict | None] = mapped_column(JSONB)  # e.g. the metric's course over the call

    session: Mapped["Session"] = relationship(back_populates="measurements")
    metric_type: Mapped["MetricType"] = relationship(back_populates="measurements")


class Finding(Base):
    """A noteworthy observation about the Session — the qualitative counterpart
    to a Measurement.

    Has no writer and no reader: the table stays for pilot data, but nothing in
    the API, the wrap-up prompt or the frontend refers to it (ADR 0051).
    """

    __tablename__ = "finding"
    finding_id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("session.session_id", ondelete="CASCADE"), index=True
    )
    metric_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("metric_type.metric_type_id", ondelete="SET NULL"), index=True
    )
    category: Mapped[str] = mapped_column(String(60))
    # Milliseconds from the start of the Session, where the finding has a
    # moment (a long pause); NULL where it characterises the whole call.
    offset_ms: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text)

    session: Mapped["Session"] = relationship(back_populates="findings")
    metric_type: Mapped["MetricType | None"] = relationship(back_populates="findings")
    feedback_points: Mapped[list["FeedbackPoint"]] = relationship(back_populates="finding")


class Feedback(Base):
    """The post-call summary for one Session, produced in the RQ worker
    (ADR 0049)."""

    __tablename__ = "feedback"
    feedback_id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("session.session_id", ondelete="CASCADE"), unique=True
    )
    summary: Mapped[str] = mapped_column(Text)
    score: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    session: Mapped["Session"] = relationship(back_populates="feedback")
    points: Mapped[list["FeedbackPoint"]] = relationship(
        back_populates="feedback",
        order_by="FeedbackPoint.position",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class FeedbackPoint(Base):
    """One individual point of a Feedback, optionally tied back to the Turn,
    Finding or MetricType it came from."""

    __tablename__ = "feedback_point"
    __table_args__ = (_one_of("kind", POINT_KINDS),)

    feedback_point_id: Mapped[int] = mapped_column(primary_key=True)
    feedback_id: Mapped[int] = mapped_column(
        ForeignKey("feedback.feedback_id", ondelete="CASCADE"), index=True
    )
    turn_id: Mapped[int | None] = mapped_column(
        ForeignKey("turn.turn_id", ondelete="SET NULL"), index=True
    )
    finding_id: Mapped[int | None] = mapped_column(
        ForeignKey("finding.finding_id", ondelete="SET NULL"), index=True
    )
    metric_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("metric_type.metric_type_id", ondelete="SET NULL"), index=True
    )
    # POINT_STRENGTH or POINT_IMPROVEMENT, see the constants above.
    kind: Mapped[str] = mapped_column(String(20))
    position: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)

    feedback: Mapped["Feedback"] = relationship(back_populates="points")
    turn: Mapped["Turn | None"] = relationship(back_populates="feedback_points")
    finding: Mapped["Finding | None"] = relationship(back_populates="feedback_points")
    metric_type: Mapped["MetricType | None"] = relationship(back_populates="feedback_points")


class AnalysisJob(Base):
    """Durable status of one async analysis/feedback job (ADR 0032)."""

    __tablename__ = "analysis_job"
    __table_args__ = (
        _one_of("kind", JOB_KINDS),
        _one_of("status", JOB_STATUSES),
    )

    job_id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("session.session_id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20))        # analysis, feedback
    status: Mapped[str] = mapped_column(String(20))      # queued, running, done, failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error_text: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    session: Mapped["Session"] = relationship(back_populates="jobs")
