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
statement per child row. Ownership edges cascade. The optional back-references
from a FeedbackPoint into rows the Session owns — the Turn and the Finding it
came from — are set to NULL, because the point still says something without
them. Every foreign key into a reference table carries no ondelete at all, the
optional ones included: a Persona or a MetricType with rows behind it must not
be deletable, and a rule that holds for one such column but not its neighbour
would be no rule at all.

Column defaults (`active`, `attempts`, `extern_id`) are Python-side only, with
no `server_default`. They apply to writes through the ORM, which is the only
writer the application has -- but unlike the deletes above, this rule does not
reach raw SQL: a row inserted by hand in `psql` has to name them itself.

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
# backend/session/models.py's utterances() is what produces them.
SPEAKER_USER = "user"
SPEAKER_PERSONA = "persona"
SPEAKERS = (SPEAKER_USER, SPEAKER_PERSONA)

# FeedbackPoint.kind (F-10): what the point is saying about the Session.
POINT_STRENGTH = "strength"
POINT_IMPROVEMENT = "improvement"
POINT_KINDS = (POINT_STRENGTH, POINT_IMPROVEMENT)

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

# Scenario.category (ADR 0072): what kind of call a Scenario is, and the
# vocabulary the library's category filter runs on. A closed CHECK-enforced
# list, unlike the free-text `scenario_type` it replaces -- that one had no
# vocabulary and no reader, and both are why it went.
#
# Four values refining F-03's three call contexts: `operations` is F-03's short
# support cases, `requirements` its consultative project talks, and `pricing` /
# `closing` split its offer-and-pricing calls, because negotiating a rate and
# getting a signature are different exercises.
#
# NULL is allowed and means "not categorised": an authored row from before this
# column existed has no value to backfill with, and inventing one would file it
# under a context nobody chose. Such a row shows under "Alle" and nowhere else.
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


# MetricType.aspect: which half of the Kennzahlen a metric belongs to -- `how`
# is the paraverbal side, `what` the verbal one. Display only, like
# `scenario.category`; backend/feedback/metrics.py assigns one per metric.
ASPECT_HOW = "how"
ASPECT_WHAT = "what"
METRIC_ASPECTS = (ASPECT_HOW, ASPECT_WHAT)


def _one_of(column: str, values: tuple[str, ...]) -> CheckConstraint:
    """A CHECK restricting `column` to `values`.

    Plain columns with a CHECK rather than a Postgres ENUM type: adding a value
    later is a one-line constraint swap instead of an ALTER TYPE that cannot run
    inside a transaction.
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

    Deliberately not the stronger `reverse => origin_session_id IS NOT NULL`:
    the origin Session is `ON DELETE SET NULL`, so a reverse whose original
    conversation has been deleted is a legitimate row that such a constraint
    would forbid the database from producing.
    """
    return CheckConstraint(
        "reverse OR reverse_brief IS NULL",
        name="brief_only_on_a_reverse",
    )


class _AuthoredContent:
    """The columns shared by the `scenario` table and, for schema symmetry, the
    `persona` table. A mixin so the set is defined once and cannot drift between
    the two.

    Three independent axes: `created_by` is authorship (ADR 0058), `tenant_id`
    is ownership by a company (ADR 0060, NULL for a shipped built-in),
    `visibility` is who may see the row. Only `scenario` rows are ever written
    with non-default values here — Personas are curated (ADR 0058). Each table
    still adds the CHECKs to its own `__table_args__`; they cannot live on the
    mixin.
    """

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
    """A company whose members share the Scenarios they author (ADR 0060,
    R-58). Seeded by hand for the pilot (`solox`, `appollo`) plus a `default`
    tenant for Users with no company. `extern_ref` is the stable key a request
    resolves to — a Keycloak Organization alias once that is enabled (phase 2),
    the seed key until then. Not deactivated: an authored row keeps pointing at
    the tenant it belonged to."""

    __tablename__ = "tenant"
    tenant_id: Mapped[int] = mapped_column(primary_key=True)
    extern_ref: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(120))


class Persona(_AuthoredContent, Base):
    """The simulated conversation partner. This table — not `backend/personas.py`
    — is the source of truth (ADR 0041); that module only seeds it.

    Personas are curated, not User-authored (ADR 0058) — the `_AuthoredContent`
    columns are here only for schema symmetry with `scenario` and never get a
    non-default value. A Persona has exactly one Language and one voice per TTS
    backend (ADR 0043).
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
    # e.g. thomas-brandt-ceo. Nullable for symmetry with `scenario.key`
    # (ADR 0058), though every Persona is a built-in and does carry a slug.
    key: Mapped[str | None] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    # Display field: the label on the selection card, in the UI language. The
    # prompt fields below are English (ADR 0043), so the two audiences this one
    # column used to serve at once are two columns now.
    role_label: Mapped[str] = mapped_column(String(120))
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


class Scenario(_AuthoredContent, Base):
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
    # Prompt fields, English (ADR 0043). `description` is the situation alone;
    # the three below carry the case (ADR 0045) -- what is true of it, what the
    # caller wants out of the call, and when the caller counts the matter as
    # settled. They are about the *case*, never about the caller, which is what
    # lets any Persona run any Scenario (ADR 0001, ADR 0015). All three may be
    # empty: a Scenario without them falls back to the improvisation the frame
    # asked for before, which is what ADR 0024's user-authored ones will be.
    description: Mapped[str] = mapped_column(Text)
    case_facts: Mapped[str] = mapped_column(Text)
    call_goal: Mapped[str] = mapped_column(Text)
    success_condition: Mapped[str] = mapped_column(Text)
    # Display/filter field, never read by the prompt (ADR 0072): one of
    # SCENARIO_CATEGORIES, or NULL for a Scenario that was never categorised.
    # The CHECK above is NULL-tolerant, which is what allows that.
    category: Mapped[str | None] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # The Session whose Feedback this Scenario was drafted from (ADR 0069),
    # NULL for every hand-authored row and every built-in. Unique, so the
    # worker cannot draft a second one for the same Session -- which is what
    # scripts/requeue_feedback.py would otherwise cause.
    # `SET NULL` rather than a cascade: a later Session may have been played on
    # this row, and `session.scenario_id` is NOT NULL with no `ondelete`
    # (ADR 0026), so the row outlives its source, deactivated (deletion.py).
    derived_from_session_id: Mapped[int | None] = mapped_column(
        # use_alter: this edge and `session.scenario_id` point at each other, and
        # without it SQLAlchemy cannot order the two tables and warns on every
        # metadata sort.
        ForeignKey("session.session_id", ondelete="SET NULL", use_alter=True),
        unique=True,
        index=True,
    )

    # --- Reverse (ADR 0070) -------------------------------------------------
    # A reverse replays one finished Session with the roles swapped: the User
    # calls and the Persona answers. A column rather than a convention in the
    # Scenario text because four readers branch on it -- the prompt casting
    # (`session/prompting.py`), the wrap-up's speaker labels, the library
    # filter and the briefing panel. That is exactly what the free-text
    # `scenario_type` label ADR 0062 removed never had.
    #
    # Distinct from `derived_from_session_id` above, which is the follow-up's
    # provenance (ADR 0069): that one says a Scenario was *written from* a
    # Session, this one says it *replays* one, and only this one changes how
    # the call is cast. A row is at most one of the two.
    reverse: Mapped[bool] = mapped_column(Boolean, default=False)
    # The Session this replays. UNIQUE, so the button is idempotent: one
    # reverse per Session, and a second press finds the row rather than making
    # a second one. `SET NULL` and not `CASCADE` -- the exception ADR 0052
    # names for a back-reference, and the direction matters here: a *reverse
    # Session* points at this row through `session.scenario_id`, so the row has
    # to outlive the conversation it came from. What it keeps is the case and a
    # briefing, never the original transcript.
    #
    # No `index=True` beside the unique constraint (ADR 0052): the unique index
    # is already an index on this column, and a second one would be dead weight
    # on every write.
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
    reverse_brief: Mapped[dict | None] = mapped_column(JSONB)

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
    # WebSocket handshake. Indexed although it is not a foreign key -- the one
    # such column in the schema. ADR 0052 left it unindexed while nothing
    # queried it; the Session history reads by this column and nothing else
    # (F-13/F-48), which is the condition ADR 0028 named for revisiting.
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

    A Turn in the domain sense is an exchange (see CONTEXT.md), and that is how
    backend/session/models.py holds it in memory — but it is stored flattened,
    one row per speaker, because that is what makes the Gesprächsprotokoll
    timestamped: each row carries its own offset into the Session.
    `utterances()` is the single place that performs the flattening.
    """

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
    # True on a Persona utterance that was cut back to the part the user
    # actually heard (ADR 0035). The transcript already carries a visible
    # "... [unterbrochen]" for the reader, but that is a display decision;
    # anything computing on it -- the interruption classification of F-51 --
    # needs a field, not a string match on a marker somebody may reword.
    # Always False on a user utterance: the Persona never talks over the user.
    interrupted: Mapped[bool] = mapped_column(Boolean, default=False)
    # What had been synthesized but not yet played when the user cut in (F-51),
    # so the wrap-up can show what the Persona had been about to say. NULL
    # everywhere else, including on an interrupted line recorded before this
    # column existed.
    #
    # Deliberately kept out of `transcript`: that column is what was actually
    # said in the call, and ADR 0035 keeps it and the model's history to the
    # heard words exactly. This is the counterfactual beside it, never part of
    # it.
    unheard_text: Mapped[str | None] = mapped_column(Text)

    session: Mapped["Session"] = relationship(back_populates="turns")
    feedback_points: Mapped[list["FeedbackPoint"]] = relationship(back_populates="turn")


class Measurement(Base):
    """One metric measured over the whole Session (ADR 0051).

    Session-level, not per Turn: none of the Kennzahlen (Redeanteil, Fragen,
    Sprechtempo, Wortanzahl, Reaktionszeit, Sprechpausen) is meaningful for a
    single utterance, and there is exactly one set of them per Session.
    """

    __tablename__ = "measurement"
    # "Exactly one set per Session" is the invariant the docstring above states;
    # this is what enforces it. Without it a second writer -- a retried job, a
    # future "recalculate" -- would store a second speaking rate for the same
    # call and the wrap-up would show both.
    __table_args__ = (UniqueConstraint("session_id", "metric_type_id"),)

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
    # F-42, phase-appropriate language: one short narrative about how the
    # trainee's register moved across the three phases of the call. Prose and
    # not a Measurement, because the thing being described is a change of tone
    # over time, which no single number carries -- and a number here would need
    # a norm nobody measured (ADR 0051). Nullable: it is written by the same
    # model call as `summary`, so a wrap-up that fell back to narrative-only,
    # or one generated before this column existed, legitimately has none.
    phase_language: Mapped[str | None] = mapped_column(Text)
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
    # POINT_STRENGTH or POINT_IMPROVEMENT, see the constants above.
    kind: Mapped[str] = mapped_column(String(20))
    position: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)

    feedback: Mapped["Feedback"] = relationship(back_populates="points")
    turn: Mapped["Turn | None"] = relationship(back_populates="feedback_points")
    finding: Mapped["Finding | None"] = relationship(back_populates="feedback_points")
    metric_type: Mapped["MetricType | None"] = relationship(back_populates="feedback_points")


class Consent(Base):
    """One recorded consent decision (ADR 0066).

    Append-only: granting, withdrawing and granting again write three rows, and
    the current state is the newest of them. A decision is a thing that
    happened at a moment, so overwriting the previous one would destroy the
    only evidence that it was ever made -- which is exactly what a consent
    record exists to keep.

    Not a foreign key to anything, for the same reason `Session.subject_id` is
    not (ADR 0031): identity lives in Keycloak and there is no local User table
    for one to point at. Indexed, because every Session that ends asks this
    table whether it may be stored.

    `version` is the wording the subject actually agreed to. A changed notice
    means a new version, which makes every earlier decision stale and prompts
    again -- consent to a text nobody showed them is not consent.
    """

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
    (ADR 0067).

    One row per subject, and only for subjects who changed the default: the
    absence of a row means the sweep applies, which is what makes the retention
    period the default rather than something each account has to be opted into.

    Deliberately its own table rather than a column on `session`. The choice is
    about an account and not about a call, and putting it on the Session would
    mean deciding, per row, what a Session written before the choice inherits.

    Not a foreign key, for the same reason `Session.subject_id` is not
    (ADR 0031): identity lives in Keycloak.
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
    """One selectable training focus (F-62, ADR 0076).

    A reference table like `metric_type`: the catalogue is shipped, seeded from
    backend/db/seed_data.py and never written by a User. What a User owns is a
    *selection* over it, which is the two tables below.

    The German display text lives in these rows, exactly as a Scenario's title
    does — it is content, not a label the interface could derive. What stays
    English is the `key` the wire and the code use (ADR 0057/0061).

    Retired goals are deactivated, never deleted: `focus_selection_goal`
    references them, and a selection made last month has to stay readable.
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

    Its own row rather than a flag derived from the goals below, because
    "picked no focus" and "was never asked" are different states and the
    interface has to tell them apart: the first must never re-open the dialog,
    the second always must. A subject who continues without a focus has a row
    here and none in `focus_selection_goal`.

    Not a foreign key, for the same reason `Session.subject_id` is not
    (ADR 0031): identity lives in Keycloak and there is no local User table.
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
    """One goal a subject is currently focusing on (ADR 0076).

    An ownership edge on the selection side (CASCADE) and a reference edge on
    the catalogue side (no ondelete), which is the same split the rest of the
    schema uses: replacing a selection removes its rows, while a FocusGoal with
    selections behind it must not be deletable at all.
    """

    __tablename__ = "focus_selection_goal"
    # The same row twice would let a subject spend two of their five slots on
    # one goal, and the count is the whole of the limit (ADR 0076).
    __table_args__ = (UniqueConstraint("selection_id", "focus_goal_id"),)

    selection_goal_id: Mapped[int] = mapped_column(primary_key=True)
    selection_id: Mapped[int] = mapped_column(
        ForeignKey("focus_selection.selection_id", ondelete="CASCADE"), index=True
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
    selection_id: Mapped[int] = mapped_column(
        ForeignKey("focus_selection.selection_id", ondelete="CASCADE"), index=True
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
