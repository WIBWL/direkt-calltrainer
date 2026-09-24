"""Persistence schema of the Calltrainer (ADR 0026); migrations and the ER
diagram are generated from it. Ownership edges cascade via `ondelete` *and*
`passive_deletes=True`; FKs into reference tables carry no `ondelete`; every FK
column is indexed (ADR 0052). Defaults are Python-side only: a row inserted
from `psql` must name `active`, `attempts` and `extern_id` itself."""

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

from backend.db.base import Base

# Session.status. The row is written once, after the Session has ended
# (ADR 0034), so there is no "running": a Session either finished normally or
# was cut short by a pipeline failure (ADR 0016).
STATUS_COMPLETED = "completed"
STATUS_ABORTED = "aborted"
SESSION_STATUSES = (STATUS_COMPLETED, STATUS_ABORTED)

# Turn.speaker. One row per utterance, so each row names exactly one speaker;
# backend/feedback/calls.py's utterances() is what produces them.
SPEAKER_USER = "user"
SPEAKER_PERSONA = "persona"
SPEAKERS = (SPEAKER_USER, SPEAKER_PERSONA)

# FeedbackPoint.kind (F-10): what the point is saying about the Session.
POINT_STRENGTH = "strength"
POINT_IMPROVEMENT = "improvement"
POINT_KINDS = (POINT_STRENGTH, POINT_IMPROVEMENT)

# Measurement.segment (ADR 0081): the whole call, or the pressing stretches and
# the rest. The whole call is a value, not NULL: Postgres treats NULLs as
# distinct in a unique index, so `UNIQUE(session, metric, segment)` would admit
# two whole-call rows for one metric.
SEGMENT_CALL = "call"
SEGMENT_PRESSURE = "pressure"
SEGMENT_REST = "rest"
MEASUREMENT_SEGMENTS = (SEGMENT_CALL, SEGMENT_PRESSURE, SEGMENT_REST)

# Consent.purpose (ADR 0066). One purpose today: storing a finished Session and
# everything hanging off it. Named rather than implied, so a second purpose --
# ADR 0065's research use of de-identified measurements is the candidate -- is
# a new value here and not a second meaning for this one.
CONSENT_SESSION_STORAGE = "session_storage"
CONSENT_PURPOSES = (CONSENT_SESSION_STORAGE,)

# Consent.status. There is no "pending": a subject who has not decided has no
# row at all, which is what the client asks about. Recording an undecided state
# would mean writing a decision nobody made.
CONSENT_GRANTED = "granted"
CONSENT_WITHDRAWN = "withdrawn"
CONSENT_STATUSES = (CONSENT_GRANTED, CONSENT_WITHDRAWN)

# AnalysisJob vocabulary (ADR 0032). Kept here next to the schema, because the
# CHECK constraints below are what actually enforce them. Only "feedback" is
# ever written: the acoustic analysis runs inline in the live path since ADR
# 0047/0048 and is persisted with the Session, so "analysis" stays inactive.
JOB_KIND_ANALYSIS = "analysis"
JOB_KIND_FEEDBACK = "feedback"
JOB_KINDS = (JOB_KIND_ANALYSIS, JOB_KIND_FEEDBACK)

# A misspelling on the way in is caught by the CHECK constraint; one on the way
# out is not -- a query for a status that does not exist simply matches nothing,
# and api/sessions.py reads "no job" as "failed". Hence names, like the three
# vocabularies above have.
JOB_QUEUED = "queued"
JOB_RUNNING = "running"
JOB_DONE = "done"
JOB_FAILED = "failed"
JOB_STATUSES = (JOB_QUEUED, JOB_RUNNING, JOB_DONE, JOB_FAILED)

# Persona.visibility / Scenario.visibility (ADR 0058): who may see an authored
# row in their library. A shipped built-in is 'public'; a User's own row starts
# 'private'; 'tenant' (added by ADR 0060) shares it with the author's company
# and requires `tenant_id` to be set (a second CHECK enforces that).
VISIBILITY_PRIVATE = "private"
VISIBILITY_TENANT = "tenant"
VISIBILITY_PUBLIC = "public"
VISIBILITIES = (VISIBILITY_PRIVATE, VISIBILITY_TENANT, VISIBILITY_PUBLIC)

# Scenario.category (ADR 0072): the kind of call, for the library filter. Four
# values refining F-03's three contexts (pricing and closing split its offer
# calls). NULL means "not categorised" and shows only under "Alle".
CATEGORY_OPERATIONS = "operations"
CATEGORY_REQUIREMENTS = "requirements"
CATEGORY_PRICING = "pricing"
CATEGORY_CLOSING = "closing"
SCENARIO_CATEGORIES = (
    CATEGORY_OPERATIONS, CATEGORY_REQUIREMENTS, CATEGORY_PRICING, CATEGORY_CLOSING,
)

# FocusGoal.group_key (ADR 0076): which part of the catalogue a goal belongs to.
# Display grouping only -- it decides which heading a card sits under and
# nothing else. The German headings live with the seed content, not here.
FOCUS_GROUP_PARAVERBAL = "paraverbal"   # the measurable core of the voice
FOCUS_GROUP_PHASES = "phases"           # along the course of the call
FOCUS_GROUP_IMPACT = "impact"           # what the call did to the other side
FOCUS_GROUP_HABIT = "habit"             # how the training itself is run
FOCUS_GROUPS = (
    FOCUS_GROUP_PARAVERBAL, FOCUS_GROUP_PHASES, FOCUS_GROUP_IMPACT, FOCUS_GROUP_HABIT,
)

# FocusGoal.evidence (ADR 0076): how far a statement about this goal can be
# derived from a recording today. Internal: it is planning information for the
# analysis work and never leaves the backend, because the aim is that every goal
# becomes measurable and a user picking one should not have to weigh up how far
# each already is.
EVIDENCE_MEASURED = "measured"        # derived from the audio or the transcript
EVIDENCE_MIXED = "mixed"              # a measurable part plus an interpreted one
EVIDENCE_INTERPRETIVE = "interpretive"  # an appraisal, not a measurement
FOCUS_EVIDENCE = (EVIDENCE_MEASURED, EVIDENCE_MIXED, EVIDENCE_INTERPRETIVE)

# FocusSelection.role: the work a User trains for. It preselects the call types
# below and is not scored on itself; seed_data.py carries the German names.
ROLE_SALES = "sales"
ROLE_SERVICE = "service"
ROLE_SUPPORT = "support"
ROLE_CONSULTING = "consulting"
ROLE_OTHER = "other"
TRAINING_ROLES = (ROLE_SALES, ROLE_SERVICE, ROLE_SUPPORT, ROLE_CONSULTING, ROLE_OTHER)


# MetricType.aspect: which half of the metrics a metric belongs to -- `how`
# is the paraverbal side, `what` the verbal one. Display only, like
# `scenario.category`; backend/feedback/metrics.py assigns one per metric.
ASPECT_HOW = "how"
ASPECT_WHAT = "what"
METRIC_ASPECTS = (ASPECT_HOW, ASPECT_WHAT)


def _one_of(column: str, values: tuple[str, ...]) -> CheckConstraint:
    """A CHECK restricting `column` to `values`. Not a Postgres ENUM: adding a
    value is a constraint swap, not an ALTER TYPE outside a transaction.
    """
    allowed = ", ".join(f"'{v}'" for v in values)
    return CheckConstraint(f"{column} IN ({allowed})", name=f"{column}_valid")


def _tenant_visibility_needs_a_tenant() -> CheckConstraint:
    """`visibility = 'tenant'` is meaningless without an owning tenant (ADR 0060),
    so the two are tied at the database."""
    return CheckConstraint(
        "visibility <> 'tenant' OR tenant_id IS NOT NULL",
        name="tenant_visibility_needs_a_tenant",
    )


def _brief_only_on_a_reverse() -> CheckConstraint:
    """The briefing belongs to a reverse and to nothing else (ADR 0070).

    Not `reverse => origin_session_id IS NOT NULL`: the origin is SET NULL on
    delete, so a reverse outliving its Session is a legitimate row."""
    return CheckConstraint(
        "reverse OR reverse_brief IS NULL",
        name="brief_only_on_a_reverse",
    )


class AuthoredContent:
    """Authorship columns shared by `scenario` and, for symmetry, `persona`.

    `created_by` (ADR 0058), `tenant_id` (ADR 0060) and `visibility` are
    independent. Each table adds the CHECKs itself; they cannot live on a mixin.
    Also what exempts a row from provision's deactivation sweep."""

    # Keycloak `sub` of the author, NULL on a shipped built-in. A plain string
    # with no foreign key, for the same reason `session.subject_id` is one
    # (ADR 0031): there is still no user table to point at.
    created_by: Mapped[str | None] = mapped_column(String(64), index=True)
    # The owning company (ADR 0060). NULL = a global built-in. Set on every
    # authored row, even a private one, so sharing is a `visibility` flip. Its
    # index is the composite `(tenant_id, visibility)` each table declares below
    # (ADR 0060) -- that covers the FK too, `tenant_id` being its first column.
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenant.tenant_id"))
    visibility: Mapped[str] = mapped_column(String(12), default=VISIBILITY_PRIVATE)
    # The id the outside world uses (ADR 0050). An authored row has no natural
    # `key` slug, and a sequential primary key must never leave the backend.
    extern_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, unique=True, default=uuid.uuid4
    )
    # A DB default rather than the app-sets-it style used elsewhere: a reference
    # row is written from the seed upsert and from the Scenario authoring
    # endpoints, and a single server-side clock keeps the two consistent.
    # `text("now()")` rather than `func.now()` so the model reads identically to
    # the `sa.text("now()")` the migration emits.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    # `onupdate` is enough because every edit to a reference row goes through
    # the ORM in backend/library.py, never raw SQL.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        onupdate=text("now()"),
    )


class Tenant(Base):
    """A company whose members share the Scenarios they author (ADR 0060, R-58).
    Seeded: the pilot tenants plus `default`. `extern_ref` is the key a request
    resolves to. Never deactivated: authored rows keep pointing at it."""

    __tablename__ = "tenant"
    tenant_id: Mapped[int] = mapped_column(primary_key=True)
    extern_ref: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(120))


class Persona(AuthoredContent, Base):
    """The simulated conversation partner; this table is the source of truth
    (ADR 0041). Curated, not User-authored (ADR 0058): the `AuthoredContent`
    columns are only for symmetry. One Language and one voice (ADR 0043).
    """

    __tablename__ = "persona"
    __table_args__ = (
        _one_of("visibility", VISIBILITIES),
        _tenant_visibility_needs_a_tenant(),
        # The visibility filter's hot path (ADR 0060). Named explicitly, as a
        # multi-column index must be; the convention only auto-names by the
        # first column.
        Index("ix_persona_tenant_id_visibility", "tenant_id", "visibility"),
    )
    persona_id: Mapped[int] = mapped_column(primary_key=True)
    # e.g. andreas-kastner-ceo. Nullable for symmetry with `scenario.key`
    # (ADR 0058), though every Persona is a built-in and does carry a slug.
    key: Mapped[str | None] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    # A path into the frontend's static files (e.g. /personas/andreas-kastner.webp),
    # not the image. Nullable; the UI then shows initials.
    avatar_url: Mapped[str | None] = mapped_column(String(200))
    # Display field: the label on the selection card, in the UI language. The
    # prompt fields below are English (ADR 0043), so the two audiences this one
    # column used to serve at once are two columns now.
    role_label: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(120))
    # Text, not capped: prose about a character.
    traits: Mapped[str] = mapped_column(Text)
    # Display counterpart of `traits`, in the UI language, for the info panel on
    # the selection card. Nullable because it is display-only: a Persona without
    # one is still fully playable, the panel just omits the line. Same split as
    # role_label/role above.
    traits_label: Mapped[str | None] = mapped_column(Text)
    behavior: Mapped[str] = mapped_column(Text)
    # German already, and the only prompt-adjacent column that is: it describes
    # what the User is meant to practise, not what the Persona does, and the
    # model never reads it.
    training_goal: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(40))
    language_code: Mapped[str] = mapped_column(ForeignKey("language.code"), index=True)
    # The Persona's voice, and the only one since KugelAudio became the whole
    # of the speech output (ADR 0103) -- a second column held the retired
    # fallback backend's voice until then. Still nullable: a Persona without a
    # voice cannot be played, and what says so is `active` below, which the
    # seed pairs with this column.
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
    # Display counterpart of `text`, in the UI language. `text` is an English
    # move the model reads (ADR 0043/0045) and must stay that way; this is the
    # same objection written for a person to read. Nullable, like
    # `persona.traits_label`.
    text_label: Mapped[str | None] = mapped_column(Text)

    persona: Mapped["Persona"] = relationship(back_populates="objections")


class Scenario(AuthoredContent, Base):
    """The situational context of a Session. Like Persona, this table is the
    source of truth and `backend/scenarios.py` only seeds it (ADR 0041)."""

    __tablename__ = "scenario"
    __table_args__ = (
        _one_of("visibility", VISIBILITIES),
        _one_of("category", SCENARIO_CATEGORIES),
        _tenant_visibility_needs_a_tenant(),
        _brief_only_on_a_reverse(),
        # The visibility filter's hot path -- `/api/scenarios` and every
        # `get_scenario` in the Session pipeline (ADR 0060).
        Index("ix_scenario_tenant_id_visibility", "tenant_id", "visibility"),
    )
    scenario_id: Mapped[int] = mapped_column(primary_key=True)
    # e.g. cold-call-followup. Nullable since ADR 0058 -- see Persona.key.
    key: Mapped[str | None] = mapped_column(String(60), unique=True)
    title: Mapped[str] = mapped_column(String(160))
    # Display field: the one-line teaser under the title on the selection card,
    # in the UI language. Deliberately short -- read at a glance, not by the
    # model.
    short_description: Mapped[str] = mapped_column(String(240))
    # Prompt fields, English (ADR 0043): the situation, then the case (ADR 0045).
    # About the case, never the caller, so any Persona can run any Scenario
    # (ADR 0001/0015). May be empty; the model then improvises.
    description: Mapped[str] = mapped_column(Text)
    case_facts: Mapped[str] = mapped_column(Text)
    # German display twins of the two above (ADR 0062). Seed-only: an authored
    # Scenario is NULL here and the API falls back to the prompt field.
    description_label: Mapped[str | None] = mapped_column(Text)
    case_facts_label: Mapped[str | None] = mapped_column(Text)
    # What the caller wants *and* the bar they judge it by, in one field. They
    # were two columns until they were merged: an author writing a goal without
    # saying when it is met writes half a case, and the prompt weighs both the
    # same way anyway -- silently, against what has actually been said, never
    # recited back.
    call_goal: Mapped[str] = mapped_column(Text)
    # Display text for the *trainee* (ADR 0054): role, room, good outcome. Never
    # put it in the prompt -- a caller handed the trainee's objective pursues it
    # (ADR 0045). May be empty.
    briefing: Mapped[str] = mapped_column(Text, default="")
    # Display/filter field, never read by the prompt (ADR 0072): one of
    # SCENARIO_CATEGORIES, or NULL for a Scenario that was never categorised.
    # The CHECK above is NULL-tolerant, which is what allows that.
    category: Mapped[str | None] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # The Session this follow-up was drafted from (ADR 0069); UNIQUE, one per
    # Session. SET NULL, not cascade: later Sessions may reference this row via
    # the NOT NULL `session.scenario_id`, so it outlives its source (deletion.py).
    derived_from_session_id: Mapped[int | None] = mapped_column(
        # use_alter: this edge and `session.scenario_id` point at each other, and
        # without it SQLAlchemy cannot order the two tables and warns on every
        # metadata sort.
        ForeignKey("session.session_id", ondelete="SET NULL", use_alter=True),
        unique=True,
        index=True,
    )

    # --- Reverse (ADR 0070) -------------------------------------------------
    # Replays one finished Session with the roles swapped. A column because the
    # prompt casting, the wrap-up, the library filter and the briefing panel
    # branch on it. A row is a reverse or a follow-up, never both.
    reverse: Mapped[bool] = mapped_column(Boolean, default=False)
    # The Session this replays. UNIQUE, so the button is idempotent. SET NULL,
    # not CASCADE: reverse Sessions reference this row, so it must outlive its
    # origin (ADR 0052). No `index=True`: the unique index already is one.
    origin_session_id: Mapped[int | None] = mapped_column(
        # use_alter for the same reason as the provenance edge above: three
        # foreign keys now run between these two tables, and without it
        # SQLAlchemy cannot order them.
        ForeignKey("session.session_id", ondelete="SET NULL", use_alter=True),
        unique=True,
    )
    # What the User reads *during* a reverse call: the Persona's own briefing,
    # turned into German prose addressed to them, plus the checklist of goals
    # (`backend/reversals.py`). NULL on every other row, which the CHECK above
    # enforces. Never part of any prompt -- a briefing the Persona could read
    # would be a briefing the Persona could act on.
    reverse_brief: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))

    # `foreign_keys` because there are now three edges between these tables --
    # this one, the provenance column above, and the reverse's origin below.
    sessions: Mapped[list["Session"]] = relationship(
        back_populates="scenario", foreign_keys="Session.scenario_id"
    )
    # No back-reference from Session on purpose -- without one the ORM issues a
    # plain DELETE and lets the database's SET NULL do the work, which is what
    # keeps deleting a Session from loading every reverse ever made of it.
    origin_session: Mapped["Session | None"] = relationship(
        foreign_keys=[origin_session_id]
    )


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
    __table_args__ = (_one_of("aspect", METRIC_ASPECTS),)
    metric_type_id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(60), unique=True)  # e.g. speaking_rate
    name: Mapped[str] = mapped_column(String(120))
    unit: Mapped[str | None] = mapped_column(String(40))
    # One of METRIC_ASPECTS. Nullable only for a key the inventory has
    # retired; the CHECK above passes for NULL.
    aspect: Mapped[str | None] = mapped_column(String(10))
    feature_id: Mapped[str | None] = mapped_column(String(10))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    measurements: Mapped[list["Measurement"]] = relationship(back_populates="metric_type")
    findings: Mapped[list["Finding"]] = relationship(back_populates="metric_type")
    feedback_points: Mapped[list["FeedbackPoint"]] = relationship(
        back_populates="metric_type"
    )


class Session(Base):
    """One simulated conversation. Written once, after it has ended (ADR 0034);
    one the client abandoned mid-call is stored as `aborted`."""

    __tablename__ = "session"
    __table_args__ = (_one_of("status", SESSION_STATUSES),)

    session_id: Mapped[int] = mapped_column(primary_key=True)
    # The unguessable id the client sees (ADR 0050). The live path passes its
    # own: session_ws.py hands it out long before this row is written.
    extern_id: Mapped[uuid.UUID] = mapped_column(Uuid, unique=True, default=uuid.uuid4)
    # Keycloak "sub" (ADR 0009/0031). Indexed though not an FK, for the history
    # (F-13/F-48). ADR 0052's exceptions, each for a named read path: this,
    # `consent.subject_id` and `AuthoredContent.created_by` -- keep the list complete.
    subject_id: Mapped[str] = mapped_column(String(64), index=True)
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
    # `foreign_keys` because two Scenario columns point back the other way --
    # the follow-up's provenance (ADR 0069) and the reverse's origin (ADR 0070).
    scenario: Mapped["Scenario"] = relationship(
        back_populates="sessions", foreign_keys=[scenario_id]
    )
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

    A domain Turn is an exchange (CONTEXT.md); stored flattened, one row per
    speaker with its own offset, by `feedback/calls.py`'s `utterances()`."""

    __tablename__ = "turn"
    __table_args__ = (
        _one_of("speaker", SPEAKERS),
        # The API orders the transcript by seq_index alone, so a duplicate
        # would make the order of those two lines arbitrary -- and arbitrary
        # differently on each read.
        UniqueConstraint("session_id", "seq_index"),
        CheckConstraint("seq_index >= 0", name="seq_index_non_negative"),
        CheckConstraint("start_offset_ms >= 0", name="start_offset_non_negative"),
        # A negative duration would be a bug in the measurement, not a
        # measurement; NULL is the legitimate way to say "not measured".
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0", name="duration_non_negative"
        ),
    )

    turn_id: Mapped[int] = mapped_column(primary_key=True)
    # No `index=True`: the unique constraint below leads with this column, so
    # it already indexes it (ADR 0052, as at `scenario.origin_session_id`).
    session_id: Mapped[int] = mapped_column(
        ForeignKey("session.session_id", ondelete="CASCADE")
    )
    # SPEAKER_USER or SPEAKER_PERSONA, see the constants above.
    speaker: Mapped[str] = mapped_column(String(10))
    seq_index: Mapped[int] = mapped_column(Integer)
    start_offset_ms: Mapped[int] = mapped_column(Integer)
    # NULL where an utterance has no measured end: a user Turn whose audio
    # could not be analysed, or a Persona line whose synthesis failed.
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    transcript: Mapped[str] = mapped_column(Text)
    # True on a Persona utterance cut back to what the user heard (ADR 0035).
    # F-51 computes on this, never on the "[unterbrochen]" display marker.
    interrupted: Mapped[bool] = mapped_column(Boolean, default=False)
    # Synthesized but unplayed when the user cut in (F-51). Kept out of
    # `transcript`, which holds the heard words only (ADR 0035).
    unheard_text: Mapped[str | None] = mapped_column(Text)
    # Raw per-utterance acoustic facts, kept because the audio is gone after the
    # call (ADR 0048) and the stretches are split later. ADR 0081's narrow
    # exception to ADR 0051: raw facts only, never statistics, never shown.
    # User rows only. JSON: nothing queries inside it (`feedback/segments.py`).
    acoustics_json: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    # True on a Persona utterance the wrap-up marked as pressing: an objection,
    # a demand, a question the trainee was under pressure to answer (ADR 0081).
    # NULL means nobody has judged this row -- no wrap-up yet, a failed one, or
    # a call recorded before the column existed -- which is deliberately not the
    # same as False.
    pressed: Mapped[bool | None] = mapped_column(Boolean)

    session: Mapped["Session"] = relationship(back_populates="turns")
    feedback_points: Mapped[list["FeedbackPoint"]] = relationship(back_populates="turn")


class Measurement(Base):
    """One metric measured over one stretch of the Session (ADR 0051, ADR 0081).

    Never per Turn. `segment` is the whole `call`, or the `pressure`/`rest`
    stretches; exactly one row per Session, metric and segment."""

    __tablename__ = "measurement"
    __table_args__ = (
        # Keeps a retried writer from storing a second figure. `segment` is
        # NOT NULL for this reason: NULLs are distinct in a unique constraint.
        UniqueConstraint("session_id", "metric_type_id", "segment"),
        _one_of("segment", MEASUREMENT_SEGMENTS),
    )

    measurement_id: Mapped[int] = mapped_column(primary_key=True)
    # Covered by the unique constraint above, which leads with it (ADR 0052).
    session_id: Mapped[int] = mapped_column(
        ForeignKey("session.session_id", ondelete="CASCADE")
    )
    metric_type_id: Mapped[int] = mapped_column(
        ForeignKey("metric_type.metric_type_id"), index=True
    )
    value: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    # One of MEASUREMENT_SEGMENTS. Python-side default like every other one in
    # this schema, so a row written from psql has to name it.
    segment: Mapped[str] = mapped_column(String(20), default=SEGMENT_CALL)
    detail_json: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))  # e.g. the metric's course over the call

    session: Mapped["Session"] = relationship(back_populates="measurements")
    metric_type: Mapped["MetricType"] = relationship(back_populates="measurements")


class Finding(Base):
    """An event at a moment in the Session, never a figure judged against a
    threshold (ADR 0051). Written per hard interruption (F-51). `description` is
    personal data, reached by every deletion path through the Session cascade."""

    __tablename__ = "finding"
    __table_args__ = (
        # Same invariant as Turn's offsets, which are checked the same way.
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
    # The only foreign key in this file without an explicit `index=True`, and
    # the exception is only apparent: `unique` already creates the index, and
    # ADR 0052 is about the index existing, not about how it got there.
    session_id: Mapped[int] = mapped_column(
        ForeignKey("session.session_id", ondelete="CASCADE"), unique=True
    )
    summary: Mapped[str] = mapped_column(Text)
    # F-42: how the register moved across the call's phases. Prose, not a
    # Measurement (ADR 0056). Nullable for older or fallback wrap-ups.
    phase_language: Mapped[str | None] = mapped_column(Text)
    # Whether the tone suited this call's occasion (ADR 0079). Prose: no measured
    # norm exists (ADR 0051/0056). Nullable like the column above.
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
    # No ondelete, unlike the two above: those point at rows the Session owns,
    # this one at a reference table, which must stay undeletable while anything
    # references it.
    metric_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("metric_type.metric_type_id"), index=True
    )
    # The F-62 focus goal this point is about (ADR 0080), so points can be counted
    # across trainings -- a closed vocabulary, since two spellings would count as
    # two. Reference table, so no ondelete. NULL: no matching goal, key omitted
    # by the model, or written before the column existed.
    focus_goal_id: Mapped[int | None] = mapped_column(
        ForeignKey("focus_goal.focus_goal_id"), index=True
    )
    # POINT_STRENGTH or POINT_IMPROVEMENT, see the constants above.
    kind: Mapped[str] = mapped_column(String(20))
    position: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)

    feedback: Mapped["Feedback"] = relationship(back_populates="points")
    turn: Mapped["Turn | None"] = relationship(back_populates="feedback_points")
    finding: Mapped["Finding | None"] = relationship(back_populates="feedback_points")
    metric_type: Mapped["MetricType | None"] = relationship(back_populates="feedback_points")
    focus_goal: Mapped["FocusGoal | None"] = relationship()


class Consent(Base):
    """One recorded consent decision (ADR 0066).

    Append-only, newest row wins: overwriting would destroy the evidence. No FK
    (identity is Keycloak's, ADR 0031). `version` is the wording agreed to; a
    new one makes every earlier decision stale."""

    __tablename__ = "consent"
    __table_args__ = (
        _one_of("purpose", CONSENT_PURPOSES),
        _one_of("status", CONSENT_STATUSES),
    )

    consent_id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[str] = mapped_column(String(64), index=True)
    # CONSENT_SESSION_STORAGE, see the constants above.
    purpose: Mapped[str] = mapped_column(String(40))
    version: Mapped[str] = mapped_column(String(20))
    # CONSENT_GRANTED or CONSENT_WITHDRAWN.
    status: Mapped[str] = mapped_column(String(20))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RetentionPreference(Base):
    """Whether one subject's Sessions are swept after the retention period
    (ADR 0067). A row only for subjects who changed the default: no row means
    the sweep applies. Per account, not per Session; no FK (ADR 0031).
    """

    __tablename__ = "retention_preference"

    preference_id: Mapped[int] = mapped_column(primary_key=True)
    # Unique, not merely indexed: a subject has one answer to this question,
    # and two rows would make the sweep's behaviour depend on which it read.
    subject_id: Mapped[str] = mapped_column(String(64), unique=True)
    # False suspends the sweep for this subject. Named for what it does rather
    # than for the exception, so the column reads the same way the switch does.
    auto_delete: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FocusGoal(Base):
    """One selectable training focus (F-62, ADR 0076): a seeded reference table
    with German display text and an English `key`. Retired goals are
    deactivated, never deleted, since selections reference them.
    """

    __tablename__ = "focus_goal"
    __table_args__ = (
        _one_of("group_key", FOCUS_GROUPS),
        _one_of("evidence", FOCUS_EVIDENCE),
    )

    focus_goal_id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(40), unique=True)  # e.g. speaking_pace
    title: Mapped[str] = mapped_column(String(120))
    # The one line under the title on the card.
    caption: Mapped[str] = mapped_column(String(240))
    # The paragraph behind the "i". Longer than a card can carry and the place
    # where the goal says what it actually looks at.
    info: Mapped[str] = mapped_column(Text)
    # `group_key`, not `group`: GROUP is a reserved word in SQL and a column of
    # that name would need quoting in every hand-written statement.
    group_key: Mapped[str] = mapped_column(String(20))
    # EVIDENCE_MEASURED / _MIXED / _INTERPRETIVE, see the constants above.
    # Internal, deliberately: api/focus.py does not serve it.
    evidence: Mapped[str] = mapped_column(String(20))
    # Display order inside the group. Not the primary key: the catalogue is
    # reordered by editing the seed, which must not renumber anybody's rows.
    position: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    selections: Mapped[list["FocusSelectionGoal"]] = relationship(
        back_populates="focus_goal"
    )


class FocusSelection(Base):
    """That one subject has answered the focus question, and when (ADR 0076).

    Its own row because "picked no focus" and "never asked" must differ, or the
    dialog re-opens forever. No FK (ADR 0031).
    """

    __tablename__ = "focus_selection"
    __table_args__ = (_one_of("role", TRAINING_ROLES),)

    selection_id: Mapped[int] = mapped_column(primary_key=True)
    # Unique, not merely indexed: a subject has one current focus, and two rows
    # would make the answer depend on which one was read first.
    subject_id: Mapped[str] = mapped_column(String(64), unique=True)
    # When the question was first answered. Kept apart from `updated_at` so a
    # later change does not erase the fact that the initial choice was made.
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # One of TRAINING_ROLES, or NULL for a subject who gave none -- including
    # everyone who answered before the question existed.
    role: Mapped[str | None] = mapped_column(String(20))

    goals: Mapped[list["FocusSelectionGoal"]] = relationship(
        back_populates="selection", cascade="all, delete-orphan", passive_deletes=True
    )
    categories: Mapped[list["FocusSelectionCategory"]] = relationship(
        back_populates="selection", cascade="all, delete-orphan", passive_deletes=True
    )


class FocusSelectionGoal(Base):
    """One goal a subject is currently focusing on (ADR 0076). CASCADE from the
    selection, no ondelete towards the catalogue.
    """

    __tablename__ = "focus_selection_goal"
    # The same row twice would let a subject spend two of their five slots on
    # one goal, and the count is the whole of the limit (ADR 0076).
    __table_args__ = (UniqueConstraint("selection_id", "focus_goal_id"),)

    selection_goal_id: Mapped[int] = mapped_column(primary_key=True)
    # Covered by the unique constraint above, which leads with it (ADR 0052).
    selection_id: Mapped[int] = mapped_column(
        ForeignKey("focus_selection.selection_id", ondelete="CASCADE")
    )
    focus_goal_id: Mapped[int] = mapped_column(
        ForeignKey("focus_goal.focus_goal_id"), index=True
    )

    selection: Mapped["FocusSelection"] = relationship(back_populates="goals")
    focus_goal: Mapped["FocusGoal"] = relationship(back_populates="selections")


class FocusSelectionCategory(Base):
    """One kind of call a subject says they take (F-62).

    The same vocabulary as `scenario.category`, which is what lets it steer the
    Scenario recommendations. Owned by the selection, like its goals.
    """

    __tablename__ = "focus_selection_category"
    __table_args__ = (
        _one_of("category", SCENARIO_CATEGORIES),
        UniqueConstraint("selection_id", "category"),
    )

    selection_category_id: Mapped[int] = mapped_column(primary_key=True)
    # Covered by the unique constraint above, which leads with it (ADR 0052).
    selection_id: Mapped[int] = mapped_column(
        ForeignKey("focus_selection.selection_id", ondelete="CASCADE")
    )
    category: Mapped[str] = mapped_column(String(20))

    selection: Mapped["FocusSelection"] = relationship(back_populates="categories")


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
