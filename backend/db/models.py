"""
Persistence schema of the Calltrainer (ADR 0026).

Single source of truth: both the Alembic migrations and the ER diagram are
derived from these classes, so neither can drift from the schema.

Conventions: one concept is one class is one table; table and column names are
English and follow the domain glossary in CONTEXT.md, so a term means the same
thing in the schema as it does in the code around it. Relationships that own
their children carry a delete cascade, so removing a Session takes its whole
subtree with it while the shared reference entities stay.

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
    — is the source of truth; that module only seeds it (ADR 0024 has Users
    authoring their own Personas, which have to live here).

    A Persona has exactly one Language and one voice, so both are attributes
    here rather than something a User picks per Session.
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
    tts_voice: Mapped[str] = mapped_column(String(60))
    # Only used when TTS_BACKEND=kugelaudio, hence nullable.
    kugelaudio_voice_id: Mapped[int | None] = mapped_column(Integer)
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
    source of truth and `backend/scenarios.py` only seeds it."""

    __tablename__ = "scenario"
    scenario_id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(60), unique=True)  # e.g. cold-call-followup
    # Not "type": that shadows the builtin wherever a row is unpacked.
    scenario_type: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    # Retired Scenarios are deactivated, never deleted: Session rows reference
    # them, and a past Session has to stay readable.
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
    """One measurable dimension of speaking behaviour, e.g. speaking rate."""

    __tablename__ = "metric_type"
    metric_type_id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(60), unique=True)  # e.g. intonation, speaking_rate
    name: Mapped[str] = mapped_column(String(120))
    unit: Mapped[str | None] = mapped_column(String(40))
    feature_id: Mapped[str | None] = mapped_column(String(10))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    measurements: Mapped[list["Measurement"]] = relationship(back_populates="metric_type")
    findings: Mapped[list["Finding"]] = relationship(back_populates="metric_type")


class Session(Base):
    """One simulated conversation. Written once, after it has ended (ADR 0034);
    a Session that the client abandoned mid-call never reaches this table."""

    __tablename__ = "session"
    __table_args__ = (_one_of("status", SESSION_STATUSES),)

    session_id: Mapped[int] = mapped_column(primary_key=True)
    # The id the client sees. Separate from the primary key so the wire never
    # exposes a guessable sequence number, and so the row can still be written
    # at the end of the Session rather than having to exist at its start.
    # Defaulted so a caller that has no public id yet still gets a valid one.
    # The live Session path does pass its own: session_ws.py has to hand the id
    # to the client when the socket opens, long before this row is written.
    extern_id: Mapped[uuid.UUID] = mapped_column(Uuid, unique=True, default=uuid.uuid4)
    # Pseudonym, not an anonymisation: a random UUID per Session keeps Sessions
    # unlinkable, but the transcript itself can still identify a person, so this
    # stays personal data (ADR 0031). Becomes the Keycloak "sub" claim once
    # ADR 0009's authentication exists.
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
    feedback: Mapped["Feedback | None"] = relationship(
        back_populates="session", cascade="all, delete-orphan", passive_deletes=True
    )
    jobs: Mapped[list["AnalysisJob"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", passive_deletes=True
    )


class Turn(Base):
    """One exchange within a Session: the user's utterance and the Persona's
    reply to it (see CONTEXT.md's "Turn" entry) — both halves in one row, not
    one row per speaker.

    The Session's opening Turn has no user half, because the Persona speaks
    first: its `user_transcript` is empty and `user_duration_ms` is NULL.
    The same holds for a final Turn cut short by a pipeline failure (ADR 0016),
    where the Persona half stays empty instead.

    Ordering comes from `seq_index` alone (per Session, starting at 1); no
    absolute offset into the Session is stored, since a paired Turn has two
    start times and nothing reads them — the Session's audio is not persisted
    (ADR 0034), so there is no timeline to align against.
    """

    __tablename__ = "turn"
    __table_args__ = (
        CheckConstraint("seq_index >= 1", name="seq_index_positive"),
        # The client supplies the user half; a negative duration would be a bug
        # on the wire rather than a measurement.
        CheckConstraint(
            "user_duration_ms IS NULL OR user_duration_ms >= 0",
            name="user_duration_non_negative",
        ),
        CheckConstraint(
            "persona_duration_ms IS NULL OR persona_duration_ms >= 0",
            name="persona_duration_non_negative",
        ),
    )

    turn_id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("session.session_id", ondelete="CASCADE"), index=True
    )
    seq_index: Mapped[int] = mapped_column(Integer)
    user_transcript: Mapped[str] = mapped_column(Text)
    persona_transcript: Mapped[str] = mapped_column(Text)
    # Nullable because a half can be absent (see above). Needed for speaking
    # rate (F-36), talk-time share (F-24) and fluency (F-51), none of which
    # can be derived from the transcript text.
    user_duration_ms: Mapped[int | None] = mapped_column(Integer)
    persona_duration_ms: Mapped[int | None] = mapped_column(Integer)

    session: Mapped["Session"] = relationship(back_populates="turns")
    feedback_points: Mapped[list["FeedbackPoint"]] = relationship(back_populates="turn")
    measurements: Mapped[list["Measurement"]] = relationship(
        back_populates="turn", cascade="all, delete-orphan", passive_deletes=True
    )
    findings: Mapped[list["Finding"]] = relationship(
        back_populates="turn", cascade="all, delete-orphan", passive_deletes=True
    )


class Measurement(Base):
    """One metric measured on the *user's* half of a Turn.

    Every paraverbal metric (F-35 to F-38, F-51) describes how the trainee
    spoke; the Persona's half is synthesized speech, so measuring it says
    nothing about the user. That is what lets a Turn hold both speakers in one
    row without `turn_id` becoming ambiguous here.
    """

    __tablename__ = "measurement"
    measurement_id: Mapped[int] = mapped_column(primary_key=True)
    turn_id: Mapped[int] = mapped_column(
        ForeignKey("turn.turn_id", ondelete="CASCADE"), index=True
    )
    metric_type_id: Mapped[int] = mapped_column(
        ForeignKey("metric_type.metric_type_id"), index=True
    )
    value: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    detail_json: Mapped[dict | None] = mapped_column(JSONB)  # e.g. the metric's course over the turn

    turn: Mapped["Turn"] = relationship(back_populates="measurements")
    metric_type: Mapped["MetricType"] = relationship(back_populates="measurements")


class Finding(Base):
    """A noteworthy observation at one point inside the user's utterance — the
    qualitative counterpart to a Measurement, and like it always about the
    user's half of the Turn."""

    __tablename__ = "finding"
    finding_id: Mapped[int] = mapped_column(primary_key=True)
    turn_id: Mapped[int] = mapped_column(
        ForeignKey("turn.turn_id", ondelete="CASCADE"), index=True
    )
    metric_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("metric_type.metric_type_id", ondelete="SET NULL"), index=True
    )
    category: Mapped[str] = mapped_column(String(60))
    # Relative to the start of the user's utterance in this Turn, for the same
    # reason Measurement attaches to the user's half only (see Measurement).
    offset_ms: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text)

    turn: Mapped["Turn"] = relationship(back_populates="findings")
    metric_type: Mapped["MetricType | None"] = relationship(back_populates="findings")
    feedback_points: Mapped[list["FeedbackPoint"]] = relationship(back_populates="finding")


class Feedback(Base):
    """The post-call summary for one Session."""

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
        back_populates="feedback", cascade="all, delete-orphan", passive_deletes=True
    )


class FeedbackPoint(Base):
    """One individual point of a Feedback, optionally tied back to the Turn or
    Finding it came from."""

    __tablename__ = "feedback_point"
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
    text: Mapped[str] = mapped_column(Text)

    feedback: Mapped["Feedback"] = relationship(back_populates="points")
    turn: Mapped["Turn | None"] = relationship(back_populates="feedback_points")
    finding: Mapped["Finding | None"] = relationship(back_populates="feedback_points")


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
