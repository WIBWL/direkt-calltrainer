"""
Datenbank-Anbindung: Engine + Session-Factory.

Zentrale Stelle, ueber die App und Worker mit Postgres sprechen. Die
Verbindungs-URL kommt aus der Umgebung (DATABASE_URL) — so kann sie je
nach Kontext unterschiedlich gesetzt werden (Mac: localhost, Container: db).

Voraussetzung: DATABASE_URL muss gesetzt sein. Im Container liefert das
das env_file (.env); in lokalen Skripten vorher load_dotenv() aufrufen.
"""
import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.environ["DATABASE_URL"]

# pool_pre_ping prueft eine Verbindung vor Gebrauch -> keine "stale connections".
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope() -> "Session":
    """Session mit automatischem commit / rollback / close.

    Nutzung:
        with session_scope() as db:
            db.add(obj)
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
