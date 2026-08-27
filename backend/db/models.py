"""
Persistence schema of the Calltrainer (ADR 0026).

Single source of truth: both the Alembic migrations and the ER diagram are
derived from these classes, so neither can drift from the schema.

Conventions: one concept is one class is one table; table and column names
are German, matching the domain vocabulary. Relationships that own their
children carry a delete cascade, so removing a Session takes its whole
subtree with it while the shared reference entities stay.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, String, Integer, Numeric, Text, DateTime, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base


class Persona(Base):
    """The simulated conversation partner. This table — not `backend/personas.py`
    — is the source of truth; that module only seeds it (ADR 0024 has Users
    authoring their own Personas, which have to live here).

    A Persona has exactly one Language and one voice, so both are attributes
    here rather than something a User picks per Session.
    """

    __tablename__ = "persona"
    persona_id: Mapped[int] = mapped_column(primary_key=True)
    schluessel: Mapped[str] = mapped_column(String(60), unique=True)  # e.g. tech-averse-management
    name: Mapped[str] = mapped_column(String(120))
    rolle: Mapped[str] = mapped_column(String(120))
    haltung: Mapped[str] = mapped_column(String(120))
    verhalten: Mapped[str] = mapped_column(Text)
    trainingsziel: Mapped[str] = mapped_column(Text)
    schwierigkeitsgrad: Mapped[str] = mapped_column(String(40))
    sprache_code: Mapped[str] = mapped_column(ForeignKey("sprache.sprache_code"))
    tts_voice: Mapped[str] = mapped_column(String(60))
    # Only used when TTS_BACKEND=kugelaudio, hence nullable.
    kugelaudio_voice_id: Mapped[int | None] = mapped_column(Integer)
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True)

    sprache: Mapped["Sprache"] = relationship(back_populates="personas")
    einwaende: Mapped[list["PersonaEinwand"]] = relationship(
        back_populates="persona",
        order_by="PersonaEinwand.reihenfolge",
        cascade="all, delete-orphan",
    )
    sessions: Mapped[list["Session"]] = relationship(back_populates="persona")


class PersonaEinwand(Base):
    """A typical objection of a Persona, kept as ordered rows rather than as a
    repeating group inside the persona row (ADR 0026)."""

    __tablename__ = "persona_einwand"
    einwand_id: Mapped[int] = mapped_column(primary_key=True)
    persona_id: Mapped[int] = mapped_column(ForeignKey("persona.persona_id"))
    reihenfolge: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)

    persona: Mapped["Persona"] = relationship(back_populates="einwaende")


class Szenario(Base):
    """The situational context of a Session. Like Persona, this table is the
    source of truth and `backend/scenarios.py` only seeds it."""

    __tablename__ = "szenario"
    szenario_id: Mapped[int] = mapped_column(primary_key=True)
    schluessel: Mapped[str] = mapped_column(String(60), unique=True)  # e.g. cold-call-followup
    typ: Mapped[str] = mapped_column(String(60))
    titel: Mapped[str] = mapped_column(String(160))
    beschreibung: Mapped[str] = mapped_column(Text)
    # Retired Szenarien are deactivated, never deleted: Session rows reference
    # them, and a past Session has to stay readable.
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True)

    sessions: Mapped[list["Session"]] = relationship(back_populates="szenario")


class Sprache(Base):
    __tablename__ = "sprache"
    sprache_code: Mapped[str] = mapped_column(String(8), primary_key=True)
    bezeichnung: Mapped[str] = mapped_column(String(60))

    personas: Mapped[list["Persona"]] = relationship(back_populates="sprache")
    sessions: Mapped[list["Session"]] = relationship(back_populates="sprache")


class MetrikTyp(Base):
    __tablename__ = "metrik_typ"
    metrik_typ_id: Mapped[int] = mapped_column(primary_key=True)
    schluessel: Mapped[str] = mapped_column(String(60), unique=True)  # e.g. intonation, tempo
    bezeichnung: Mapped[str] = mapped_column(String(120))
    einheit: Mapped[str | None] = mapped_column(String(40))
    feature_id: Mapped[str | None] = mapped_column(String(10))
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True)

    messungen: Mapped[list["Messung"]] = relationship(back_populates="metrik_typ")
    befunde: Mapped[list["Befund"]] = relationship(back_populates="metrik_typ")


class Session(Base):
    __tablename__ = "session"
    session_id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[str] = mapped_column(String(64))  # pseudonym, later the Keycloak "sub" claim (ADR 0031)
    persona_id: Mapped[int] = mapped_column(ForeignKey("persona.persona_id"))
    szenario_id: Mapped[int] = mapped_column(ForeignKey("szenario.szenario_id"))
    # Deliberately duplicated from Persona.sprache_code rather than derived:
    # this records the Language the Session actually ran in, which must stay
    # correct even if the Persona is later edited (ADR 0024) or deactivated.
    sprache_code: Mapped[str] = mapped_column(ForeignKey("sprache.sprache_code"))
    # A Session row is written once, after the Session has ended (ADR 0034),
    # so "laufend" never occurs: "beendet" covers a Session the user or the
    # Persona ended normally, "abgebrochen" one cut short by a pipeline
    # failure (ADR 0016).
    status: Mapped[str] = mapped_column(String(20))
    gestartet_am: Mapped[datetime] = mapped_column(DateTime)
    beendet_am: Mapped[datetime | None] = mapped_column(DateTime)

    persona: Mapped["Persona"] = relationship(back_populates="sessions")
    szenario: Mapped["Szenario"] = relationship(back_populates="sessions")
    sprache: Mapped["Sprache"] = relationship(back_populates="sessions")
    turns: Mapped[list["Turn"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    feedback: Mapped["Feedback | None"] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    jobs: Mapped[list["AnalysisJob"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class Turn(Base):
    """One exchange within a Session: the user's utterance and the Persona's
    reply to it (see CONTEXT.md's "Turn" entry) — both halves in one row, not
    one row per speaker.

    The Session's opening Turn has no user half, because the Persona speaks
    first: its `nutzer_transkript` is empty and `nutzer_dauer_ms` is NULL.
    The same holds for a final Turn cut short by a pipeline failure (ADR 0016),
    where the Persona half stays empty instead.

    Ordering comes from `seq_index` alone (per Session, starting at 1); no
    absolute offset into the Session is stored, since a paired Turn has two
    start times and nothing reads them — the Session's audio is not persisted
    (ADR 0034), so there is no timeline to align against.
    """

    __tablename__ = "turn"
    turn_id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("session.session_id"))
    seq_index: Mapped[int] = mapped_column(Integer)
    nutzer_transkript: Mapped[str] = mapped_column(Text)
    persona_transkript: Mapped[str] = mapped_column(Text)
    # Nullable because a half can be absent (see above). Needed for speaking
    # rate (F-36), talk-time share (F-24) and fluency (F-51), none of which
    # can be derived from the transcript text.
    nutzer_dauer_ms: Mapped[int | None] = mapped_column(Integer)
    persona_dauer_ms: Mapped[int | None] = mapped_column(Integer)

    session: Mapped["Session"] = relationship(back_populates="turns")
    feedbackpunkte: Mapped[list["Feedbackpunkt"]] = relationship(back_populates="turn")
    messungen: Mapped[list["Messung"]] = relationship(
        back_populates="turn", cascade="all, delete-orphan"
    )
    befunde: Mapped[list["Befund"]] = relationship(
        back_populates="turn", cascade="all, delete-orphan"
    )


class Messung(Base):
    """One metric measured on the *user's* half of a Turn.

    Every paraverbal metric (F-35 to F-38, F-51) describes how the trainee
    spoke; the Persona's half is synthesized speech, so measuring it says
    nothing about the user. That is what lets a Turn hold both speakers in one
    row without `turn_id` becoming ambiguous here.
    """

    __tablename__ = "messung"
    messung_id: Mapped[int] = mapped_column(primary_key=True)
    turn_id: Mapped[int] = mapped_column(ForeignKey("turn.turn_id"))
    metrik_typ_id: Mapped[int] = mapped_column(ForeignKey("metrik_typ.metrik_typ_id"))
    wert: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    detail_json: Mapped[dict | None] = mapped_column(JSONB)  # e.g. the metric's course over the turn

    turn: Mapped["Turn"] = relationship(back_populates="messungen")
    metrik_typ: Mapped["MetrikTyp"] = relationship(back_populates="messungen")


class Befund(Base):
    __tablename__ = "befund"
    befund_id: Mapped[int] = mapped_column(primary_key=True)
    turn_id: Mapped[int] = mapped_column(ForeignKey("turn.turn_id"))
    metrik_typ_id: Mapped[int | None] = mapped_column(ForeignKey("metrik_typ.metrik_typ_id"))
    kategorie: Mapped[str] = mapped_column(String(60))
    # Relative to the start of the user's utterance in this Turn, for the same
    # reason Messung attaches to the user's half only (see Messung).
    offset_ms: Mapped[int] = mapped_column(Integer)
    beschreibung: Mapped[str] = mapped_column(Text)

    turn: Mapped["Turn"] = relationship(back_populates="befunde")
    metrik_typ: Mapped["MetrikTyp | None"] = relationship(back_populates="befunde")
    feedbackpunkte: Mapped[list["Feedbackpunkt"]] = relationship(back_populates="befund")


class Feedback(Base):
    __tablename__ = "feedback"
    feedback_id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("session.session_id"), unique=True)
    zusammenfassung: Mapped[str] = mapped_column(Text)
    score: Mapped[int | None] = mapped_column(Integer)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime)

    session: Mapped["Session"] = relationship(back_populates="feedback")
    punkte: Mapped[list["Feedbackpunkt"]] = relationship(
        back_populates="feedback", cascade="all, delete-orphan"
    )


class Feedbackpunkt(Base):
    __tablename__ = "feedbackpunkt"
    feedbackpunkt_id: Mapped[int] = mapped_column(primary_key=True)
    feedback_id: Mapped[int] = mapped_column(ForeignKey("feedback.feedback_id"))
    turn_id: Mapped[int | None] = mapped_column(ForeignKey("turn.turn_id"))
    befund_id: Mapped[int | None] = mapped_column(ForeignKey("befund.befund_id"))
    text: Mapped[str] = mapped_column(Text)

    feedback: Mapped["Feedback"] = relationship(back_populates="punkte")
    turn: Mapped["Turn | None"] = relationship(back_populates="feedbackpunkte")
    befund: Mapped["Befund | None"] = relationship(back_populates="feedbackpunkte")


class AnalysisJob(Base):
    __tablename__ = "analysis_job"
    job_id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("session.session_id"))
    art: Mapped[str] = mapped_column(String(20))         # analyse, feedback
    status: Mapped[str] = mapped_column(String(20))      # queued, running, done, failed
    versuche: Mapped[int] = mapped_column(Integer, default=0)
    fehlertext: Mapped[str | None] = mapped_column(Text)
    aktualisiert_am: Mapped[datetime] = mapped_column(DateTime)

    session: Mapped["Session"] = relationship(back_populates="jobs")
