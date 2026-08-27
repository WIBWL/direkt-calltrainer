"""The migrations have to be runnable in both directions.

`downgrade()` is the half that never gets exercised by normal work, and
autogenerate reliably produces a broken one — unnamed constraints it cannot
drop, and NOT NULL columns added without a backfill. These tests run the whole
chain rather than the newest revision, so a later revision cannot quietly break
an earlier one's downgrade.
"""
from sqlalchemy import create_engine, inspect

from backend.db.models import Base
from tests.conftest import alembic_downgrade, alembic_upgrade


def _table_names(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def _columns(url: str, table: str) -> set[str]:
    engine = create_engine(url)
    try:
        return {c["name"] for c in inspect(engine).get_columns(table)}
    finally:
        engine.dispose()


def test_upgrade_creates_every_table_the_models_declare(empty_database: str) -> None:
    """A migration that forgets a table would leave the ORM querying nothing."""
    alembic_upgrade(empty_database)

    created = _table_names(empty_database)
    missing = set(Base.metadata.tables) - created
    assert not missing, f"Migrations do not create: {sorted(missing)}"


def test_downgrade_to_base_removes_the_schema_again(empty_database: str) -> None:
    """Every downgrade has to undo its upgrade, all the way back to nothing."""
    alembic_upgrade(empty_database)
    alembic_downgrade(empty_database, "base")

    remaining = _table_names(empty_database) - {"alembic_version"}
    assert remaining == set(), f"Left behind after downgrade: {sorted(remaining)}"


def test_full_round_trip_restores_the_same_schema(empty_database: str) -> None:
    """Down and up again must land on exactly the schema we started from."""
    alembic_upgrade(empty_database)
    before = {table: _columns(empty_database, table) for table in _table_names(empty_database)}

    alembic_downgrade(empty_database, "base")
    alembic_upgrade(empty_database)

    after = {table: _columns(empty_database, table) for table in _table_names(empty_database)}
    assert after == before


def test_turn_holds_both_speakers_in_one_row(empty_database: str) -> None:
    """Guards the decision that a Turn is one exchange, not one utterance
    (CONTEXT.md's "Turn" entry) — the shape the analysis tables depend on."""
    alembic_upgrade(empty_database)

    columns = _columns(empty_database, "turn")
    assert {"nutzer_transkript", "persona_transkript"} <= columns
    assert {"nutzer_dauer_ms", "persona_dauer_ms"} <= columns
    # Dropped with the pairing: a paired Turn has no single speaker or start.
    assert "sprecher" not in columns
    assert "start_offset_ms" not in columns
