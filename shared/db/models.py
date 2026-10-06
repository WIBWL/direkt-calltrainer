"""The schema (ADR 0026). Ownership edges cascade via `ondelete` and
`passive_deletes`; FKs into reference tables carry no `ondelete`; every FK is
indexed (ADR 0052). Defaults are Python-side only, so a row inserted from `psql`
must name `active`, `attempts` and `extern_id`."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.db.base import Base

# Written once after the call (ADR 0034), so there is no "running".
STATUS_COMPLETED = "completed"
STATUS_ABORTED = "aborted"
SESSION_STATUSES = (STATUS_COMPLETED, STATUS_ABORTED)

SPEAKER_USER = "user"
SPEAKER_PERSONA = "persona"
SPEAKERS = (SPEAKER_USER, SPEAKER_PERSONA)

POINT_STRENGTH = "strength"
POINT_IMPROVEMENT = "improvement"
POINT_KINDS = (POINT_STRENGTH, POINT_IMPROVEMENT)

# Not NULL for the whole call: NULLs are distinct in a unique index.
SEGMENT_CALL = "call"
SEGMENT_PRESSURE = "pressure"
SEGMENT_REST = "rest"
MEASUREMENT_SEGMENTS = (SEGMENT_CALL, SEGMENT_PRESSURE, SEGMENT_REST)

CONSENT_SESSION_STORAGE = "session_storage"
CONSENT_PURPOSES = (CONSENT_SESSION_STORAGE,)

# No "pending": an undecided subject has no row.
CONSENT_GRANTED = "granted"
CONSENT_WITHDRAWN = "withdrawn"
CONSENT_STATUSES = (CONSENT_GRANTED, CONSENT_WITHDRAWN)

# Only "feedback" is written; "analysis" stays an inactive value (ADR 0032).
JOB_KIND_ANALYSIS = "analysis"
JOB_KIND_FEEDBACK = "feedback"
JOB_KINDS = (JOB_KIND_ANALYSIS, JOB_KIND_FEEDBACK)

JOB_QUEUED = "queued"
JOB_RUNNING = "running"
JOB_DONE = "done"
JOB_FAILED = "failed"
JOB_STATUSES = (JOB_QUEUED, JOB_RUNNING, JOB_DONE, JOB_FAILED)

# 'tenant' requires `tenant_id` (a second CHECK).
VISIBILITY_PRIVATE = "private"
VISIBILITY_TENANT = "tenant"
VISIBILITY_PUBLIC = "public"
VISIBILITIES = (VISIBILITY_PRIVATE, VISIBILITY_TENANT, VISIBILITY_PUBLIC)

# Display and filter only (ADR 0072). NULL means uncategorised.
CATEGORY_OPERATIONS = "operations"
CATEGORY_REQUIREMENTS = "requirements"
CATEGORY_PRICING = "pricing"
CATEGORY_CLOSING = "closing"
SCENARIO_CATEGORIES = (
    CATEGORY_OPERATIONS, CATEGORY_REQUIREMENTS, CATEGORY_PRICING, CATEGORY_CLOSING,
)

# Display grouping only (ADR 0076).
FOCUS_GROUP_PARAVERBAL = "paraverbal"
FOCUS_GROUP_PHASES = "phases"
FOCUS_GROUP_IMPACT = "impact"
FOCUS_GROUP_HABIT = "habit"
FOCUS_GROUPS = (
    FOCUS_GROUP_PARAVERBAL, FOCUS_GROUP_PHASES, FOCUS_GROUP_IMPACT, FOCUS_GROUP_HABIT,
)

# Internal planning data, never served (ADR 0076).
EVIDENCE_MEASURED = "measured"
EVIDENCE_MIXED = "mixed"
EVIDENCE_INTERPRETIVE = "interpretive"
FOCUS_EVIDENCE = (EVIDENCE_MEASURED, EVIDENCE_MIXED, EVIDENCE_INTERPRETIVE)

# Preselects call types; scored on nothing.
ROLE_SALES = "sales"
ROLE_SERVICE = "service"
ROLE_SUPPORT = "support"
ROLE_CONSULTING = "consulting"
ROLE_OTHER = "other"
TRAINING_ROLES = (ROLE_SALES, ROLE_SERVICE, ROLE_SUPPORT, ROLE_CONSULTING, ROLE_OTHER)


# Display only (ADR 0082).
ASPECT_HOW = "how"
ASPECT_WHAT = "what"
METRIC_ASPECTS = (ASPECT_HOW, ASPECT_WHAT)


def _one_of(column: str, values: tuple[str, ...]) -> CheckConstraint:
    """Not an ENUM: adding a value is a constraint swap, not ALTER TYPE (ADR 0053)."""
    allowed = ", ".join(f"'{v}'" for v in values)
    return CheckConstraint(f"{column} IN ({allowed})", name=f"{column}_valid")


def _tenant_visibility_needs_a_tenant() -> CheckConstraint:
    return CheckConstraint(
        "visibility <> 'tenant' OR tenant_id IS NOT NULL",
        name="tenant_visibility_needs_a_tenant",
    )


def _brief_only_on_a_reverse() -> CheckConstraint:
    """Not `reverse => origin_session_id IS NOT NULL`: the origin is SET NULL
    on delete, so a reverse may outlive its Session."""
    return CheckConstraint(
        "reverse OR reverse_brief IS NULL",
        name="brief_only_on_a_reverse",
    )


class ReferenceRow:
    extern_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, unique=True, default=uuid.uuid4
    )
    # Server default: the seed upsert and the authoring routes share one clock.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    # `onupdate` suffices: every edit goes through the ORM in library.py.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        onupdate=text("now()"),
    )


class AuthoredContent(ReferenceRow):
    """Authorship columns (ADR 0058/0060). Also what exempts a row from the
    provision sweep's deactivation."""

    # Keycloak `sub`, NULL on a built-in; no FK (ADR 0031).
    created_by: Mapped[str | None] = mapped_column(String(64), index=True)
    # Set even on private rows, so sharing is a `visibility` flip. Indexed by
    # the composite `(tenant_id, visibility)` each table declares.
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenant.tenant_id"))
    visibility: Mapped[str] = mapped_column(String(12), default=VISIBILITY_PRIVATE)


class Tenant(Base):
    """Never deactivated: authored rows keep pointing at it (ADR 0060)."""

    __tablename__ = "tenant"
    tenant_id: Mapped[int] = mapped_column(primary_key=True)
    extern_ref: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(120))


class Persona(ReferenceRow, Base):
    """Curated, so no authorship columns (ADR 0058)."""

    __tablename__ = "persona"
    persona_id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str | None] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    # A path into the frontend's static files; NULL shows initials.
    avatar_url: Mapped[str | None] = mapped_column(String(200))
    # Display label in the UI language; the prompt fields are English (ADR 0043).
    role_label: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(120))
    traits: Mapped[str] = mapped_column(Text)
    # Display twin of `traits`; optional.
    traits_label: Mapped[str | None] = mapped_column(Text)
    behavior: Mapped[str] = mapped_column(Text)
    # German, and never read by the model.
    training_goal: Mapped[str] = mapped_column(Text)
    language_code: Mapped[str] = mapped_column(ForeignKey("language.code"), index=True)
    # NULL means unplayable, which `active` says.
    kugelaudio_voice_id: Mapped[int | None] = mapped_column(Integer)
    # A `hard` Persona gets the anti-repeat nudge that offers no ground.
    hard: Mapped[bool] = mapped_column(Boolean, default=False)
    # Deactivated, never deleted: past Sessions reference it.
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
    __tablename__ = "persona_objection"
    objection_id: Mapped[int] = mapped_column(primary_key=True)
    persona_id: Mapped[int] = mapped_column(
        ForeignKey("persona.persona_id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    # Display twin of the English move in `text`.
    text_label: Mapped[str | None] = mapped_column(Text)

    persona: Mapped["Persona"] = relationship(back_populates="objections")


class Scenario(AuthoredContent, Base):
    __tablename__ = "scenario"
    __table_args__ = (
        _one_of("visibility", VISIBILITIES),
        _one_of("category", SCENARIO_CATEGORIES),
        _tenant_visibility_needs_a_tenant(),
        _brief_only_on_a_reverse(),
        Index("ix_scenario_tenant_id_visibility", "tenant_id", "visibility"),
    )
    scenario_id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str | None] = mapped_column(String(60), unique=True)
    title: Mapped[str] = mapped_column(String(160))
    short_description: Mapped[str] = mapped_column(String(240))
    # Prompt fields, English (ADR 0043/0045): about the case, never the caller.
    description: Mapped[str] = mapped_column(Text)
    case_facts: Mapped[str] = mapped_column(Text)
    # German display twins; NULL on authored rows, which fall back to the prompt field.
    description_label: Mapped[str | None] = mapped_column(Text)
    case_facts_label: Mapped[str | None] = mapped_column(Text)
    # What the caller wants and the bar they judge it by, in one field.
    call_goal: Mapped[str] = mapped_column(Text)
    # For the trainee only; never in the prompt (ADR 0054).
    briefing: Mapped[str] = mapped_column(Text, default="")
    # Never read by the prompt (ADR 0072).
    category: Mapped[str | None] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # The follow-up's source (ADR 0069), one per Session. SET NULL: later
    # Sessions may play this row, so it outlives its source.
    derived_from_session_id: Mapped[int | None] = mapped_column(
        # use_alter: this table and `session` reference each other.
        ForeignKey("session.session_id", ondelete="SET NULL", use_alter=True),
        unique=True,
        index=True,
    )

    # A reverse (ADR 0070); never also a follow-up.
    reverse: Mapped[bool] = mapped_column(Boolean, default=False)
    # UNIQUE makes the button idempotent; SET NULL so it outlives its origin.
    origin_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("session.session_id", ondelete="SET NULL", use_alter=True),
        unique=True,
    )
    # The User's briefing during a reverse. Never in any prompt.
    reverse_brief: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))

    sessions: Mapped[list["Session"]] = relationship(
        back_populates="scenario", foreign_keys="Session.scenario_id"
    )
    # No back-reference on purpose: deleting a Session then leaves SET NULL to
    # the database instead of loading every reverse of it.
    origin_session: Mapped["Session | None"] = relationship(
        foreign_keys=[origin_session_id]
    )


class Language(Base):
    """Never deactivated: a Session keeps pointing at its code."""

    __tablename__ = "language"
    code: Mapped[str] = mapped_column(String(8), primary_key=True)
    name: Mapped[str] = mapped_column(String(60))

    personas: Mapped[list["Persona"]] = relationship(back_populates="language")
    sessions: Mapped[list["Session"]] = relationship(back_populates="language")


class MetricType(Base):
    """Seeded from the inventory in shared/feedback/metrics.py (ADR 0051)."""

    __tablename__ = "metric_type"
    __table_args__ = (_one_of("aspect", METRIC_ASPECTS),)
    metric_type_id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    unit: Mapped[str | None] = mapped_column(String(40))
    # Nullable only for a retired key.
    aspect: Mapped[str | None] = mapped_column(String(10))
    feature_id: Mapped[str | None] = mapped_column(String(10))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    measurements: Mapped[list["Measurement"]] = relationship(back_populates="metric_type")
    findings: Mapped[list["Finding"]] = relationship(back_populates="metric_type")
    feedback_points: Mapped[list["FeedbackPoint"]] = relationship(
        back_populates="metric_type"
    )


class Session(Base):
    """Written once after the call (ADR 0034); a disconnect stores `aborted`."""

    __tablename__ = "session"
    __table_args__ = (_one_of("status", SESSION_STATUSES),)

    session_id: Mapped[int] = mapped_column(primary_key=True)
    # The id the client sees (ADR 0050), handed out before this row exists.
    extern_id: Mapped[uuid.UUID] = mapped_column(Uuid, unique=True, default=uuid.uuid4)
    # Keycloak `sub`; indexed for the history (ADR 0052's named exceptions).
    subject_id: Mapped[str] = mapped_column(String(64), index=True)
    persona_id: Mapped[int] = mapped_column(ForeignKey("persona.persona_id"), index=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("scenario.scenario_id"), index=True)
    # Copied, not derived: the language the call ran in.
    language_code: Mapped[str] = mapped_column(ForeignKey("language.code"), index=True)
    status: Mapped[str] = mapped_column(String(20))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    persona: Mapped["Persona"] = relationship(back_populates="sessions")
    scenario: Mapped["Scenario"] = relationship(
        back_populates="sessions", foreign_keys=[scenario_id]
    )
    language: Mapped["Language"] = relationship(back_populates="sessions")
    turns: Mapped[list["Turn"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", passive_deletes=True
    )
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
    """One utterance of one speaker; a domain Turn is stored as one row per speaker."""

    __tablename__ = "turn"
    __table_args__ = (
        _one_of("speaker", SPEAKERS),
        # The transcript orders by seq_index alone.
        UniqueConstraint("session_id", "seq_index"),
        CheckConstraint("seq_index >= 0", name="seq_index_non_negative"),
        CheckConstraint("start_offset_ms >= 0", name="start_offset_non_negative"),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0", name="duration_non_negative"
        ),
    )

    turn_id: Mapped[int] = mapped_column(primary_key=True)
    # Indexed by the unique constraint, which leads with it.
    session_id: Mapped[int] = mapped_column(
        ForeignKey("session.session_id", ondelete="CASCADE")
    )
    speaker: Mapped[str] = mapped_column(String(10))
    seq_index: Mapped[int] = mapped_column(Integer)
    start_offset_ms: Mapped[int] = mapped_column(Integer)
    # NULL: no measured end (analysis or synthesis failed).
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    transcript: Mapped[str] = mapped_column(Text)
    # F-51 computes on this, never on the "[unterbrochen]" marker.
    interrupted: Mapped[bool] = mapped_column(Boolean, default=False)
    # Synthesized but never played; kept out of `transcript`.
    unheard_text: Mapped[str | None] = mapped_column(Text)
    # Raw facts, never statistics, kept because the audio is gone (ADR 0081).
    acoustics_json: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    # Marked pressing by the wrap-up. NULL = not judged, which is not False.
    pressed: Mapped[bool | None] = mapped_column(Boolean)

    session: Mapped["Session"] = relationship(back_populates="turns")
    feedback_points: Mapped[list["FeedbackPoint"]] = relationship(back_populates="turn")


class Measurement(Base):
    """One metric over one stretch: the whole `call`, `pressure` or `rest`."""

    __tablename__ = "measurement"
    __table_args__ = (
        # `segment` is NOT NULL because NULLs are distinct in a unique constraint.
        UniqueConstraint("session_id", "metric_type_id", "segment"),
        _one_of("segment", MEASUREMENT_SEGMENTS),
    )

    measurement_id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("session.session_id", ondelete="CASCADE")
    )
    metric_type_id: Mapped[int] = mapped_column(
        ForeignKey("metric_type.metric_type_id"), index=True
    )
    value: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    segment: Mapped[str] = mapped_column(String(20), default=SEGMENT_CALL)
    detail_json: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))

    session: Mapped["Session"] = relationship(back_populates="measurements")
    metric_type: Mapped["MetricType"] = relationship(back_populates="measurements")


class Finding(Base):
    """An event at a moment, never a figure judged against a threshold (ADR 0051)."""

    __tablename__ = "finding"
    __table_args__ = (
        CheckConstraint(
            "offset_ms IS NULL OR offset_ms >= 0", name="offset_non_negative"
        ),
    )

    finding_id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("session.session_id", ondelete="CASCADE"), index=True
    )
    metric_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("metric_type.metric_type_id"), index=True
    )
    category: Mapped[str] = mapped_column(String(60))
    # From Session start; NULL for the whole call.
    offset_ms: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text)

    session: Mapped["Session"] = relationship(back_populates="findings")
    metric_type: Mapped["MetricType | None"] = relationship(back_populates="findings")
    feedback_points: Mapped[list["FeedbackPoint"]] = relationship(back_populates="finding")


class Feedback(Base):
    __tablename__ = "feedback"
    feedback_id: Mapped[int] = mapped_column(primary_key=True)
    # `unique` creates the index ADR 0052 asks for.
    session_id: Mapped[int] = mapped_column(
        ForeignKey("session.session_id", ondelete="CASCADE"), unique=True
    )
    summary: Mapped[str] = mapped_column(Text)
    # Prose, not a Measurement (ADR 0056); NULL when the model omitted it.
    phase_language: Mapped[str | None] = mapped_column(Text)
    # ADR 0079; NULL like the column above.
    tone_fit: Mapped[str | None] = mapped_column(Text)
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
    # No ondelete: it points at a reference table.
    metric_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("metric_type.metric_type_id"), index=True
    )
    # ADR 0080. NULL: nothing fitted, or the model omitted it.
    focus_goal_id: Mapped[int | None] = mapped_column(
        ForeignKey("focus_goal.focus_goal_id"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20))
    position: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)

    feedback: Mapped["Feedback"] = relationship(back_populates="points")
    turn: Mapped["Turn | None"] = relationship(back_populates="feedback_points")
    finding: Mapped["Finding | None"] = relationship(back_populates="feedback_points")
    metric_type: Mapped["MetricType | None"] = relationship(back_populates="feedback_points")
    focus_goal: Mapped["FocusGoal | None"] = relationship()


class Consent(Base):
    """Append-only, newest row wins (ADR 0066); a new `version` makes earlier
    decisions stale."""

    __tablename__ = "consent"
    __table_args__ = (
        _one_of("purpose", CONSENT_PURPOSES),
        _one_of("status", CONSENT_STATUSES),
    )

    consent_id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[str] = mapped_column(String(64), index=True)
    purpose: Mapped[str] = mapped_column(String(40))
    version: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RetentionPreference(Base):
    """A row only for subjects who switched the sweep off (ADR 0067)."""

    __tablename__ = "retention_preference"

    preference_id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[str] = mapped_column(String(64), unique=True)
    auto_delete: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FocusGoal(Base):
    """A seeded reference table (ADR 0076); retired goals are deactivated."""

    __tablename__ = "focus_goal"
    __table_args__ = (
        _one_of("group_key", FOCUS_GROUPS),
        _one_of("evidence", FOCUS_EVIDENCE),
    )

    focus_goal_id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(40), unique=True)
    title: Mapped[str] = mapped_column(String(120))
    caption: Mapped[str] = mapped_column(String(240))
    info: Mapped[str] = mapped_column(Text)
    # GROUP is reserved in SQL.
    group_key: Mapped[str] = mapped_column(String(20))
    # Never served (ADR 0076).
    evidence: Mapped[str] = mapped_column(String(20))
    # Display order; reordering the seed must not renumber rows.
    position: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    selections: Mapped[list["FocusSelectionGoal"]] = relationship(
        back_populates="focus_goal"
    )


class FocusSelection(Base):
    """Its own row so that "picked no focus" differs from "never asked"."""

    __tablename__ = "focus_selection"
    __table_args__ = (_one_of("role", TRAINING_ROLES),)

    selection_id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[str] = mapped_column(String(64), unique=True)
    # First answer, kept apart from later edits.
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    role: Mapped[str | None] = mapped_column(String(20))

    goals: Mapped[list["FocusSelectionGoal"]] = relationship(
        back_populates="selection", cascade="all, delete-orphan", passive_deletes=True
    )
    categories: Mapped[list["FocusSelectionCategory"]] = relationship(
        back_populates="selection", cascade="all, delete-orphan", passive_deletes=True
    )


class FocusSelectionGoal(Base):
    __tablename__ = "focus_selection_goal"
    # The same goal twice would spend two of the five slots.
    __table_args__ = (UniqueConstraint("selection_id", "focus_goal_id"),)

    selection_goal_id: Mapped[int] = mapped_column(primary_key=True)
    # Indexed by the unique constraint.
    selection_id: Mapped[int] = mapped_column(
        ForeignKey("focus_selection.selection_id", ondelete="CASCADE")
    )
    focus_goal_id: Mapped[int] = mapped_column(
        ForeignKey("focus_goal.focus_goal_id"), index=True
    )

    selection: Mapped["FocusSelection"] = relationship(back_populates="goals")
    focus_goal: Mapped["FocusGoal"] = relationship(back_populates="selections")


class FocusSelectionCategory(Base):
    """A kind of call the subject takes, in `scenario.category`'s vocabulary."""

    __tablename__ = "focus_selection_category"
    __table_args__ = (
        _one_of("category", SCENARIO_CATEGORIES),
        UniqueConstraint("selection_id", "category"),
    )

    selection_category_id: Mapped[int] = mapped_column(primary_key=True)
    # Indexed by the unique constraint.
    selection_id: Mapped[int] = mapped_column(
        ForeignKey("focus_selection.selection_id", ondelete="CASCADE")
    )
    category: Mapped[str] = mapped_column(String(20))

    selection: Mapped["FocusSelection"] = relationship(back_populates="categories")


class AnalysisJob(Base):
    __tablename__ = "analysis_job"
    __table_args__ = (
        _one_of("kind", JOB_KINDS),
        _one_of("status", JOB_STATUSES),
    )

    job_id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("session.session_id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error_text: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    session: Mapped["Session"] = relationship(back_populates="jobs")
