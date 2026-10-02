"""The migration chain, in both directions (ADR 0027, ADR 0052, ADR 0053).

The whole chain runs, so a later revision cannot break an earlier downgrade.
Only on an *empty* database: `d7f41c9b3a26` widened `persona.traits`, so rolling
back past it fails on seeded data, deliberately. A green run is no promise a
deployed schema can be rolled back. Also pins the naming convention (ADR 0053)
and that every foreign-key column is indexed (ADR 0052)."""
from sqlalchemy import create_engine, inspect, text

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


def test_turn_holds_one_utterance_per_row(empty_database: str) -> None:
    """A stored Turn is one utterance of one speaker, not an exchange (ADR 0026).

    Flattened by `utterances()`, which gives every line its own offset for the
    timestamped Gesprächsprotokoll.
    """
    alembic_upgrade(empty_database)

    columns = _columns(empty_database, "turn")
    assert {"speaker", "transcript", "start_offset_ms", "duration_ms"} <= columns
    # A row names one speaker, so there are no per-speaker halves on it.
    assert "user_transcript" not in columns
    assert "persona_transcript" not in columns


def _constraint_names(url: str) -> list[tuple[str, str, str]]:
    """(table, kind, name) for every constraint the application owns."""
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            return [
                (row.table_name, row.kind, row.name)
                for row in conn.execute(
                    text(
                        "SELECT conrelid::regclass::text AS table_name, contype AS kind, "
                        "conname AS name FROM pg_constraint "
                        "WHERE connamespace = 'public'::regnamespace "
                        "AND contype IN ('p','u','f','c') "
                        # Alembic's own bookkeeping table, not part of the schema.
                        "AND conrelid <> 'alembic_version'::regclass"
                    )
                )
            ]
    finally:
        engine.dispose()


def test_every_constraint_follows_the_naming_convention(empty_database: str) -> None:
    """The convention on Base.metadata is what stops autogenerate emitting
    unnamed constraints, whose downgrade cannot run. A constraint that slipped
    through with a database-assigned name would silently reintroduce that."""
    alembic_upgrade(empty_database)

    expected_prefix = {"p": "pk_", "u": "uq_", "f": "fk_", "c": "ck_"}
    offenders = [
        (table, name)
        for table, kind, name in _constraint_names(empty_database)
        if not name.startswith(expected_prefix[kind])
    ]
    assert not offenders, f"Constraints not following the convention: {offenders}"


def test_every_foreign_key_column_is_indexed(empty_database: str) -> None:
    """Postgres indexes the referenced primary key but never the referencing
    side, so an unindexed foreign key turns every parent delete into a
    sequential scan of the child table."""
    alembic_upgrade(empty_database)
    engine = create_engine(empty_database)
    try:
        with engine.connect() as conn:
            unindexed = list(
                conn.execute(
                    text(
                        """
                        SELECT c.conrelid::regclass::text AS tbl, a.attname AS col
                          FROM pg_constraint c
                          JOIN pg_attribute a
                            ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
                         WHERE c.contype = 'f'
                           AND NOT EXISTS (
                               SELECT 1 FROM pg_index i
                                WHERE i.indrelid = c.conrelid
                                  AND a.attnum = i.indkey[0]
                           )
                        """
                    )
                )
            )
    finally:
        engine.dispose()
    assert not unindexed, f"Foreign keys without an index: {unindexed}"
