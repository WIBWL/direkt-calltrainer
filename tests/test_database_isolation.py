"""No test may reach the development database.

This is a guard on the test setup itself, not on the application. It is easy to
lose by accident: `backend/clients/config.py` calls `load_dotenv()` at import
time, so the developer's real POSTGRES_* would be in the environment for the
whole session unless conftest claims those names first with unusable values.
If that ordering is ever disturbed, a test that calls `session_scope()` without
asking for a database fixture writes into the database someone is developing
against — silently, and only on their machine.

Covers:
  ADR 0034  a Session is written once, to a real database — which is what makes
            an accidental connection from a test destructive rather than inert
"""
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

from backend.db.session import build_database_url

# pylint: disable=missing-function-docstring


def test_plain_tests_get_the_placeholder_settings():
    """The values conftest claims, not the ones in .env."""
    assert os.environ["POSTGRES_USER"] == "calltrainer-test-no-such-user"
    assert os.environ["POSTGRES_DB"] == "calltrainer-test-no-such-database"


def test_the_placeholder_settings_cannot_actually_connect():
    """The point of the placeholders: an accidental connection fails loudly
    instead of reaching a real database."""
    engine = create_engine(build_database_url(), connect_args={"connect_timeout": 5})
    try:
        with pytest.raises(OperationalError):
            with engine.connect():
                pass
    finally:
        engine.dispose()


def test_db_session_does_not_touch_the_environment(db_session):
    """`db_session` builds its own engine from the throwaway URL, so it never
    needs the settings — which is why the placeholders still stand here."""
    assert os.environ["POSTGRES_DB"] == "calltrainer-test-no-such-database"
    assert db_session.bind.url.database.startswith("calltrainer_test_")


def test_app_database_points_the_application_at_the_throwaway_one(app_database):
    """`app_database` is the fixture that does override them, because anything
    going through session_scope() reads them rather than taking a URL."""
    assert os.environ["POSTGRES_DB"].startswith("calltrainer_test_")
    assert build_database_url().database == os.environ["POSTGRES_DB"]
    assert build_database_url().render_as_string(hide_password=False) == app_database


def test_the_override_does_not_outlive_the_test():
    """...and afterwards the placeholders are back. Ordering matters here: this
    test only means something because the one above ran first."""
    assert os.environ["POSTGRES_DB"] == "calltrainer-test-no-such-database"
