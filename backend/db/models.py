"""
Persistence schema of the Calltrainer (ADR 0027).

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
    __tablename__ = "persona"
    persona_id: Mapped[int] = mapped_column(primary_key=True)
    schluessel: Mapped[str] = mapped_column(String(60), unique=True)  # e.g. tech-averse-management
    name: Mapped[str] = mapped_column(String(120))
    rolle: Mapped[str] = mapped_column(String(120))
    haltung: Mapped[str] = mapped_column(String(120))
    verhalten: Mapped[str] = mapped_column(Text)
    trainingsziel: Mapped[str] = mapped_column(Text)
    schwierigkeitsgrad: Mapped[str] = mapped_column(String(40))
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True)

    einwaende: Mapped[list["PersonaEinwand"]] = relationship(
        back_populates="persona",
        order_by="PersonaEinwand.reihenfolge",
        cascade="all, delete-orphan",
    )
    sessions: Mapped[list["Session"]] = relationship(back_populates="persona")


class PersonaEinwand(Base):
    """A typical objection of a Persona, kept as ordered rows rather than as a
    repeating group inside the persona row (ADR 0027)."""

    __tablename__ = "persona_einwand"
    einwand_id: Mapped[int] = mapped_column(primary_key=True)
    persona_id: Mapped[int] = mapped_column(ForeignKey("persona.persona_id"))
    reihenfolge: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)

    persona: Mapped["Persona"] = relationship(back_populates="einwaende")


class Szenario(Base):
    __tablename__ = "szenario"
    szenario_id: Mapped[int] = mapped_column(primary_key=True)
    schluessel: Mapped[str] = mapped_column(String(60), unique=True)  # e.g. cold-call-followup
    typ: Mapped[str] = mapped_column(String(60))
    titel: Mapped[str] = mapped_column(String(160))
    beschreibung: Mapped[str] = mapped_column(Text)

    sessions: Mapped[list["Session"]] = relationship(back_populates="szenario")


class Sprache(Base):
    __tablename__ = "sprache"
    sprache_code: Mapped[str] = mapped_column(String(8), primary_key=True)
    bezeichnung: Mapped[str] = mapped_column(String(60))

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
    subject_id: Mapped[str] = mapped_column(String(64))  # pseudonym, later the Keycloak "sub" claim (ADR 0032)
    persona_id: Mapped[int] = mapped_column(ForeignKey("persona.persona_id"))
    szenario_id: Mapped[int] = mapped_column(ForeignKey("szenario.szenario_id"))
    sprache_code: Mapped[str] = mapped_column(ForeignKey("sprache.sprache_code"))
    status: Mapped[str] = mapped_column(String(20))      # laufend, beendet, abgebrochen
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
    __tablename__ = "turn"
    turn_id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("session.session_id"))
    sprecher: Mapped[str] = mapped_column(String(10))    # nutzer, persona
    seq_index: Mapped[int] = mapped_column(Integer)
    start_offset_ms: Mapped[int] = mapped_column(Integer)
    dauer_ms: Mapped[int] = mapped_column(Integer)
    transkript: Mapped[str] = mapped_column(Text)

    session: Mapped["Session"] = relationship(back_populates="turns")
    feedbackpunkte: Mapped[list["Feedbackpunkt"]] = relationship(back_populates="turn")
    messungen: Mapped[list["Messung"]] = relationship(
        back_populates="turn", cascade="all, delete-orphan"
    )
    befunde: Mapped[list["Befund"]] = relationship(
        back_populates="turn", cascade="all, delete-orphan"
    )


class Messung(Base):
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
