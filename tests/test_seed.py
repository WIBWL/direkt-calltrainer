"""The seed runs on every application start (backend/db/provision.py, called
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
    tables = ["language", "persona", "persona_objection", "scenario", "metric_type"]
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
                    "INSERT INTO persona (key, name, role, traits, behavior,"
                    " training_goal, difficulty, language_code, tts_voice, active)"
                    " VALUES ('retired-persona', 'Alt', 'Alt', 'alt', 'alt', '', 'mittel',"
                    " 'de', 'de_male', true)"
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
