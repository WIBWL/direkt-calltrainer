"""No test can reach the development database."""
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

from shared.db.session import build_database_url


def test_plain_tests_get_the_placeholder_settings():
    assert make_url(os.environ["POSTGRES_URL"]).database == "no-such-database"
    assert "POSTGRES_PASSWORD" not in os.environ


def test_the_placeholder_settings_cannot_actually_connect():
    engine = create_engine(build_database_url(), connect_args={"connect_timeout": 5})
    try:
        with pytest.raises(OperationalError):
            with engine.connect():
                pass
    finally:
        engine.dispose()


def test_db_session_does_not_touch_the_environment(db_session):
    assert make_url(os.environ["POSTGRES_URL"]).database == "no-such-database"
    assert db_session.bind.url.database.startswith("calltrainer_test_")


def test_app_database_points_the_application_at_the_throwaway_one(app_database):
    assert make_url(os.environ["POSTGRES_URL"]).database.startswith("calltrainer_test_")
    assert build_database_url().render_as_string(hide_password=False) == app_database


def test_the_override_does_not_outlive_the_test():
    assert make_url(os.environ["POSTGRES_URL"]).database == "no-such-database"
