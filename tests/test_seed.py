"""The reference tables the application seeds itself (ADR 0041, ADR 0057,
ADR 0058, ADR 0076).

The seed runs on every application start (backend/db/provision.py, called
from the lifespan handler), so running it twice must not change anything the
first run produced.

Exercised through scripts/seed_reference_data.py as a subprocess rather than by
importing provision(), because the script is the path a human takes — including
its `load_dotenv` and its module-level `sys.path` juggling, both of which only
behave that way as a script. The application calls the same provision().
"""
import os
import subprocess
import sys

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
                    "WHERE language_code IS NULL OR tts_voice IS NULL OR tts_voice = ''"
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
                    " behavior, training_goal, difficulty, language_code, tts_voice,"
                    " active, visibility)"
                    " VALUES ('retired-persona', gen_random_uuid(), 'Alt', 'Alt', 'Alt',"
                    " 'alt', 'alt', '', 'mittel', 'de', 'de_male', true, 'public')"
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
    """The same rule for the metric inventory, which ADR 0057 already claims it
    follows: when a metric key was renamed, the old row is deactivated.

    It was not, for a long time. Every German key from before that rename stayed
    active beside its English replacement, and both carry the same display name
    ("Redeanteil" for `redeanteil` and for `talk_share`), so anything reading the
    inventory saw each renamed metric twice. Measurements reference these rows,
    which is why this is a flag and not a delete.
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
# `scenario` holds authored Scenarios, Folgeszenarien and Rollentausch rows
# beside the shipped ones, and the seed runs at every application start. The
# three tests below pin the two halves of that: the sweep still retires a
# built-in, and it does not touch a row somebody wrote.

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
    """The one that bites.

    An authored row carries no `key` today, so the sweep passes it by through
    SQL's three-valued logic alone -- `NULL NOT IN (...)` is NULL, not TRUE --
    and the previous test would pass with no guard in `_deactivate_missing` at
    all. Give `scenario.key` a default or backfill it, two tables away from the
    sweep, and every User's library would be deactivated on the next boot with
    no error and nothing failing.

    So this one states the rule the sweep is supposed to follow -- the seed
    retires what the seed created, and authorship is what says so -- rather than
    the accident that currently enforces it.
    """
    assert _seed_twice_with(migrated_database, "user-picked-a-key", "keycloak-sub-1") is True
