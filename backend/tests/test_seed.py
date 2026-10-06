"""Seeding is idempotent and touches only seed rows (ADR 0041, 0057, 0058, 0076)."""
import os
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, text

from shared.tests.fixtures import PROJECT_ROOT


def _postgres_env(database_url: str) -> dict[str, str]:
    """The database setting for `database_url`, as the seed script's own
    `build_database_url()` expects to find it."""
    return {"POSTGRES_URL": database_url}


def _run_seed(database_url: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "backend.scripts.seed_reference_data"],
        cwd=PROJECT_ROOT,
        # The child inherits the suite's placeholder, so the test's own
        # database has to be named explicitly.
        env={**os.environ, **_postgres_env(database_url)},
        capture_output=True,
        text=True,
        # Asserted below instead, so a failure shows the seed's own output.
        check=False,
    )
    assert result.returncode == 0, f"Seed failed:\n{result.stdout}\n{result.stderr}"
    return result.stdout


def _counts(url: str) -> dict[str, int]:
    engine = create_engine(url)
    tables = ["language", "tenant", "persona", "persona_objection", "scenario", "metric_type"]
    try:
        with engine.connect() as conn:
            return {t: conn.execute(text(f"SELECT count(*) FROM {t}")).scalar_one() for t in tables}
    finally:
        engine.dispose()


def test_seed_populates_the_reference_tables(migrated_database: str) -> None:
    _run_seed(migrated_database)

    counts = _counts(migrated_database)
    assert counts["persona"] > 0
    assert counts["scenario"] > 0
    assert counts["language"] > 0
    assert counts["metric_type"] > 0
    assert counts["tenant"] == 1  # `default` only; companies arrive by login (ADR 0060)


def test_seed_is_idempotent(migrated_database: str) -> None:
    _run_seed(migrated_database)
    after_first = _counts(migrated_database)

    second_run = _run_seed(migrated_database)
    after_second = _counts(migrated_database)

    assert after_second == after_first
    assert "Persona 0, Scenario 0" in second_run, second_run


def test_seed_fills_language_and_voice_on_every_persona(migrated_database: str) -> None:
    _run_seed(migrated_database)

    engine = create_engine(migrated_database)
    try:
        with engine.connect() as conn:
            incomplete = conn.execute(
                text(
                    "SELECT count(*) FROM persona "
                    "WHERE language_code IS NULL "
                    "OR (active AND kugelaudio_voice_id IS NULL)"
                )
            ).scalar_one()
    finally:
        engine.dispose()
    assert incomplete == 0


def test_seed_deactivates_personas_it_no_longer_contains(migrated_database: str) -> None:
    _run_seed(migrated_database)

    engine = create_engine(migrated_database)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO persona (key, extern_id, name, role_label, role, traits,"
                    " behavior, training_goal, language_code,"
                    " kugelaudio_voice_id, active, hard)"
                    " VALUES ('retired-persona', gen_random_uuid(), 'Alt', 'Alt', 'Alt',"
                    " 'alt', 'alt', '', 'de', 1885, true, false)"
                )
            )

        _run_seed(migrated_database)

        with engine.connect() as conn:
            still_there = conn.execute(
                text("SELECT active FROM persona WHERE key = 'retired-persona'")
            ).scalar_one()
    finally:
        engine.dispose()

    assert still_there is False, "Retired Persona should be deactivated, not left active"


def test_seed_deactivates_metric_types_it_no_longer_contains(migrated_database: str) -> None:
    _run_seed(migrated_database)

    engine = create_engine(migrated_database)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO metric_type (key, name, unit, active)"
                    " VALUES ('redeanteil', 'Redeanteil', '%', true)"
                )
            )

        _run_seed(migrated_database)

        with engine.connect() as conn:
            still_there = conn.execute(
                text("SELECT active FROM metric_type WHERE key = 'redeanteil'")
            ).scalar_one()
    finally:
        engine.dispose()

    assert still_there is False, "Renamed metric type should be deactivated"


# The sweep retires built-ins, never a row somebody wrote.

_AUTHORED_SCENARIO = (
    "INSERT INTO scenario (key, extern_id, title, short_description, description,"
    " case_facts, call_goal, briefing, active, reverse, visibility,"
    " created_by, created_at, updated_at)"
    " VALUES (:key, gen_random_uuid(), 'Eigenes', 'Kurz', 'Lang', 'Fakten', 'Ziel',"
    " '', true, false, 'private', :created_by, now(), now())"
)


def _seed_twice_with(database_url: str, key, created_by: str | None) -> bool:
    """Insert one scenario row, re-run the seed, and report whether it survived."""
    _run_seed(database_url)
    engine = create_engine(database_url)
    try:
        with engine.begin() as conn:
            conn.execute(text(_AUTHORED_SCENARIO), {"key": key, "created_by": created_by})

        _run_seed(database_url)

        with engine.connect() as conn:
            return conn.execute(
                text("SELECT active FROM scenario WHERE title = 'Eigenes'")
            ).scalar_one()
    finally:
        engine.dispose()


def test_seed_deactivates_a_built_in_scenario_it_no_longer_contains(
    migrated_database: str,
) -> None:
    assert _seed_twice_with(migrated_database, "retired-scenario", None) is False


def test_seed_leaves_an_authored_scenario_alone(migrated_database: str) -> None:
    assert _seed_twice_with(migrated_database, None, "keycloak-sub-1") is True


def test_seed_leaves_an_authored_scenario_alone_even_when_it_has_a_key(
    migrated_database: str,
) -> None:
    assert _seed_twice_with(migrated_database, "user-picked-a-key", "keycloak-sub-1") is True


# The upsert must write `active` back, or a returning built-in stays invisible.

_SWEPT_TABLES = [
    ("persona", "persona_id"),
    ("scenario", "scenario_id"),
    ("focus_goal", "focus_goal_id"),
    ("metric_type", "metric_type_id"),
]


@pytest.mark.parametrize("table, primary_key", _SWEPT_TABLES)
def test_seed_brings_a_deactivated_row_back(
    migrated_database: str, table: str, primary_key: str
) -> None:
    _run_seed(migrated_database)
    engine = create_engine(migrated_database)
    try:
        with engine.begin() as conn:
            row_id = conn.execute(
                text(f"SELECT {primary_key} FROM {table}"
                     f" WHERE active AND key IS NOT NULL"
                     f" ORDER BY {primary_key} LIMIT 1")
            ).scalar_one()
            conn.execute(
                text(f"UPDATE {table} SET active = false"
                     f" WHERE {primary_key} = :row_id"),
                {"row_id": row_id},
            )

        _run_seed(migrated_database)

        with engine.connect() as conn:
            active = conn.execute(
                text(f"SELECT active FROM {table}"
                     f" WHERE {primary_key} = :row_id"),
                {"row_id": row_id},
            ).scalar_one()
    finally:
        engine.dispose()

    assert active is True, f"{table} is deactivated one way only"
