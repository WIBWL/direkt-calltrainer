"""
Zentrale Declarative Base für alle ORM-Entitäten.

Von dieser Klasse erbt jede Entität in models.py. Alembic importiert
später ihre .metadata, um daraus die Migrationen abzuleiten. Sie liegt
bewusst allein in einer eigenen Datei, damit Modelle, DB-Session und
Alembic sie unabhängig voneinander importieren können, ohne Import-Kreise.
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass