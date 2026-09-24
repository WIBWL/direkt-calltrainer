"""The reference tables the application seeds itself (ADR 0041, 0057, 0058, 0076).

The seed runs on every start, so a second run must change nothing. Run through
scripts/seed_reference_data.py as a subprocess, the path a human takes (its `load_dotenv`
and `sys.path` setup only behave that way as a script); the app calls the same provision()."""
import os
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from tests.conftest import PROJECT_ROOT


def _postgres_env(database_url: str) -> dict[str, str]:
    """The POSTGRES_* settings for `database_url`, as the seed script's own
    `build_database_url()` expects to find them."""
    url = make_url(database_url)
    return {
        "POSTGRES_USER": url.username,
        "POSTGRES_PASSWORD": url.password,
        "POSTGRES_DB": url.database,
        "POSTGRES_HOST": url.host,
        "POSTGRES_PORT": str(url.port or 5432),
    }


def _run_seed(database_url: str) -> str:
    result = subprocess.run(
        [sys.executable, "scripts/seed_reference_data.py"],
        cwd=PROJECT_ROOT,
        # These must win over the .env the script itself loads; python-dotenv
        # does not override variables that are already set, so passing them
        # through the child's environment is enough.
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
    """A migrated but unseeded database serves no Personas at all."""
    _run_seed(migrated_database)

    counts = _counts(migrated_database)
    assert counts["persona"] > 0
    assert counts["scenario"] > 0
    assert counts["language"] > 0
    assert counts["metric_type"] > 0
    assert counts["tenant"] >= 3  # solox, appollo, default (ADR 0060)


def test_seed_is_idempotent(migrated_database: str) -> None:
    """The entrypoint runs the seed on every container start."""
    _run_seed(migrated_database)
    after_first = _counts(migrated_database)

    second_run = _run_seed(migrated_database)
    after_second = _counts(migrated_database)

    assert after_second == after_first
    assert "Persona 0, Scenario 0" in second_run, second_run


def test_seed_fills_language_and_voice_on_every_persona(migrated_database: str) -> None:
    """Without these the persona table cannot replace backend/personas.py as the
    source of truth, and the session handshake has no voice to synthesize with."""
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
    """Retired Personas must disappear from the selection without being deleted —
    `session` references them, so a past Session has to stay readable."""
    _run_seed(migrated_database)

    engine = create_engine(migrated_database)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO persona (key, extern_id, name, role_label, role, traits,"
                    " behavior, training_goal, difficulty, language_code,"
                    " kugelaudio_voice_id, active, visibility)"
                    " VALUES ('retired-persona', gen_random_uuid(), 'Alt', 'Alt', 'Alt',"
                    " 'alt', 'alt', '', 'mittel', 'de', 1885, true, 'public')"
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
    """ADR 0057 for the metric inventory: a renamed metric key's old row is deactivated.

    Otherwise old and new keys share a display name and every reader sees the metric
    twice. Measurements reference these rows, hence a flag and not a delete.
    """
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


# --- The sweep must not reach User-owned rows (ADR 0058) ---------------------
#
# `scenario` also holds authored, follow-up and reverse rows, and the seed runs at
# every start: the sweep retires a built-in but never a row somebody wrote.

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
    """The sweep still does its job. Here so that the two tests below cannot be
    satisfied by simply switching it off for this table."""
    assert _seed_twice_with(migrated_database, "retired-scenario", None) is False


def test_seed_leaves_an_authored_scenario_alone(migrated_database: str) -> None:
    """A Scenario a User wrote is not a retired built-in, and the seed has no
    opinion about it (ADR 0058)."""
    assert _seed_twice_with(migrated_database, None, "keycloak-sub-1") is True


def test_seed_leaves_an_authored_scenario_alone_even_when_it_has_a_key(
    migrated_database: str,
) -> None:
    """The one that bites: an authored row *with* a key must survive the sweep.

    Keyless rows survive only by accident (`NULL NOT IN (...)` is NULL). Give `scenario.key`
    a default or backfill it and every User's library is silently deactivated on the next
    boot. Pins the rule itself: the seed retires only what the seed created."""
    assert _seed_twice_with(migrated_database, "user-picked-a-key", "keycloak-sub-1") is True


# --- The other half of the sweep: bringing a row back ------------------------
#
# The upsert must write `active` back, or a built-in that once dropped out of the seed
# (a branch, a key renamed back) stays invisible for good: text refreshed, `active`
# still False, no error. `_seed_scenarios` once left the column out.

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
    """Every swept table's seeded row is "brought back to the seed state" (provision.py),
    including `active`, so a fifth table cannot quietly repeat the bug.

    The row is picked (any seed-owned, seeded-active row), keeping the test off the content.
    """
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
