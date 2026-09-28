"""No test may reach the development database (ADR 0034).

Guards the test setup: the fixtures must claim POSTGRES_URL with an unusable value
before any package reads it, or a stray `session_scope()` writes silently into the
database the developer's sourced .env names."""
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

from shared.db.session import build_database_url


def test_plain_tests_get_the_placeholder_settings():
    """The values conftest claims, not the ones in .env."""
    assert make_url(os.environ["POSTGRES_URL"]).database == "no-such-database"
    assert "POSTGRES_PASSWORD" not in os.environ


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
    assert make_url(os.environ["POSTGRES_URL"]).database == "no-such-database"
    assert db_session.bind.url.database.startswith("calltrainer_test_")


def test_app_database_points_the_application_at_the_throwaway_one(app_database):
    """`app_database` is the fixture that does override them, because anything
    going through session_scope() reads them rather than taking a URL."""
    assert make_url(os.environ["POSTGRES_URL"]).database.startswith("calltrainer_test_")
    assert build_database_url().render_as_string(hide_password=False) == app_database


def test_the_override_does_not_outlive_the_test():
    """...and afterwards the placeholders are back. Ordering matters here: this
    test only means something because the one above ran first."""
    assert make_url(os.environ["POSTGRES_URL"]).database == "no-such-database"
