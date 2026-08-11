"""
Datenmodell "Train to Call with AI" — Option A (MVP-Kern).

Dies ist die EINZIGE Quelle der Wahrheit: Aus diesen Klassen entstehen
(a) die Datenbanktabellen (via Alembic-Migrationen) und
(b) das ER-Diagramm (via Generator-Skript).
Beide bleiben dadurch automatisch synchron.

Konvention: konzeptionelle Entität == ORM-Klasse == Tabelle.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String, Integer, Numeric, Text, DateTime, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base


class Persona(Base):
    __tablename__ = "persona"
    persona_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    rolle: Mapped[str] = mapped_column(String(120))
    haltung: Mapped[str] = mapped_column(String(120))
    schwierigkeitsgrad: Mapped[str] = mapped_column(String(40))
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True)

    sessions: Mapped[list["Session"]] = relationship(back_populates="persona")


class Szenario(Base):
    __tablename__ = "szenario"
    szenario_id: Mapped[int] = mapped_column(primary_key=True)
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
    schluessel: Mapped[str] = mapped_column(String(60), unique=True)  # intonation, tempo etc
    bezeichnung: Mapped[str] = mapped_column(String(120))
    einheit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    feature_id: Mapped[str | None] = mapped_column(String(10), nullable=True)
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True)

    messungen: Mapped[list["Messung"]] = relationship(back_populates="metrik_typ")
    befunde: Mapped[list["Befund"]] = relationship(back_populates="metrik_typ")


class Session(Base):
    __tablename__ = "session"
    session_id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[str] = mapped_column(String(64))  # pseudonym, später -> Keycloak-sub
    persona_id: Mapped[int] = mapped_column(ForeignKey("persona.persona_id"))
    szenario_id: Mapped[int] = mapped_column(ForeignKey("szenario.szenario_id"))
    sprache_code: Mapped[str] = mapped_column(ForeignKey("sprache.sprache_code"))
    status: Mapped[str] = mapped_column(String(20))      # laufend, beendet, abgebrochen
    gestartet_am: Mapped[datetime] = mapped_column(DateTime)
    beendet_am: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    persona: Mapped["Persona"] = relationship(back_populates="sessions")
    szenario: Mapped["Szenario"] = relationship(back_populates="sessions")
    sprache: Mapped["Sprache"] = relationship(back_populates="sessions")
    turns: Mapped[list["Turn"]] = relationship(back_populates="session")
    feedback: Mapped["Feedback | None"] = relationship(back_populates="session")
    jobs: Mapped[list["AnalysisJob"]] = relationship(back_populates="session")


class Turn(Base):
    __tablename__ = "turn"
    turn_id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("session.session_id"))
    sprecher: Mapped[str] = mapped_column(String(10))    # nutzer oder persona
    seq_index: Mapped[int] = mapped_column(Integer)
    start_offset_ms: Mapped[int] = mapped_column(Integer)
    dauer_ms: Mapped[int] = mapped_column(Integer)
    transkript: Mapped[str] = mapped_column(Text)

    session: Mapped["Session"] = relationship(back_populates="turns")
    messungen: Mapped[list["Messung"]] = relationship(back_populates="turn")
    befunde: Mapped[list["Befund"]] = relationship(back_populates="turn")


class Messung(Base):
    __tablename__ = "messung"
    messung_id: Mapped[int] = mapped_column(primary_key=True)
    turn_id: Mapped[int] = mapped_column(ForeignKey("turn.turn_id"))
    metrik_typ_id: Mapped[int] = mapped_column(ForeignKey("metrik_typ.metrik_typ_id"))
    wert: Mapped[float] = mapped_column(Numeric(10, 4))
    detail_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # z.B. Verlauf

    turn: Mapped["Turn"] = relationship(back_populates="messungen")
    metrik_typ: Mapped["MetrikTyp"] = relationship(back_populates="messungen")


class Befund(Base):
    __tablename__ = "befund"
    befund_id: Mapped[int] = mapped_column(primary_key=True)
    turn_id: Mapped[int] = mapped_column(ForeignKey("turn.turn_id"))
    metrik_typ_id: Mapped[int | None] = mapped_column(
        ForeignKey("metrik_typ.metrik_typ_id"), nullable=True
    )
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
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime)

    session: Mapped["Session"] = relationship(back_populates="feedback")
    punkte: Mapped[list["Feedbackpunkt"]] = relationship(back_populates="feedback")


class Feedbackpunkt(Base):
    __tablename__ = "feedbackpunkt"
    feedbackpunkt_id: Mapped[int] = mapped_column(primary_key=True)
    feedback_id: Mapped[int] = mapped_column(ForeignKey("feedback.feedback_id"))
    turn_id: Mapped[int | None] = mapped_column(ForeignKey("turn.turn_id"), nullable=True)
    befund_id: Mapped[int | None] = mapped_column(ForeignKey("befund.befund_id"), nullable=True)
    text: Mapped[str] = mapped_column(Text)

    feedback: Mapped["Feedback"] = relationship(back_populates="punkte")
    befund: Mapped["Befund | None"] = relationship(back_populates="feedbackpunkte")


class AnalysisJob(Base):
    __tablename__ = "analysis_job"
    job_id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("session.session_id"))
    art: Mapped[str] = mapped_column(String(20))         # analyse, feedback
    status: Mapped[str] = mapped_column(String(20))      # queued, running, done, failed
    versuche: Mapped[int] = mapped_column(Integer, default=0)
    fehlertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    aktualisiert_am: Mapped[datetime] = mapped_column(DateTime)

    session: Mapped["Session"] = relationship(back_populates="jobs")