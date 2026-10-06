"""Required settings and `_FILE` variants (ADR 0106)."""

import pytest

from shared.db.session import build_database_url
from shared.env import optional, required

# pylint: disable=missing-function-docstring


def test_a_set_variable_is_read(monkeypatch):
    monkeypatch.setenv("CALLTRAINER_TEST_SETTING", "value")
    assert required("CALLTRAINER_TEST_SETTING") == "value"


@pytest.mark.parametrize("value", [None, ""])
def test_an_unset_or_empty_variable_refuses(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("CALLTRAINER_TEST_SETTING", raising=False)
    else:
        monkeypatch.setenv("CALLTRAINER_TEST_SETTING", value)
    with pytest.raises(RuntimeError, match="CALLTRAINER_TEST_SETTING is required"):
        required("CALLTRAINER_TEST_SETTING")
    assert optional("CALLTRAINER_TEST_SETTING") is None


def test_the_file_variant_is_read_and_stripped(monkeypatch, tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("s3cret\n", encoding="utf-8")
    monkeypatch.delenv("CALLTRAINER_TEST_SETTING", raising=False)
    monkeypatch.setenv("CALLTRAINER_TEST_SETTING_FILE", str(secret))
    assert required("CALLTRAINER_TEST_SETTING") == "s3cret"


def test_both_at_once_refuses(monkeypatch, tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("from-file", encoding="utf-8")
    monkeypatch.setenv("CALLTRAINER_TEST_SETTING", "direct")
    monkeypatch.setenv("CALLTRAINER_TEST_SETTING_FILE", str(secret))
    with pytest.raises(RuntimeError, match="both set"):
        required("CALLTRAINER_TEST_SETTING")


def test_an_unreadable_file_names_itself(monkeypatch, tmp_path):
    monkeypatch.delenv("CALLTRAINER_TEST_SETTING", raising=False)
    monkeypatch.setenv("CALLTRAINER_TEST_SETTING_FILE", str(tmp_path / "missing.txt"))
    with pytest.raises(RuntimeError, match="missing.txt"):
        required("CALLTRAINER_TEST_SETTING")


def test_the_database_url_takes_any_postgres_scheme(monkeypatch):
    monkeypatch.setenv("POSTGRES_URL", "postgres://user:pw@db:5432/calltrainer")
    url = build_database_url()
    assert url.drivername == "postgresql+psycopg"
    assert (url.username, url.password, url.host, url.database) == ("user", "pw", "db", "calltrainer")


def test_the_password_setting_replaces_the_one_in_the_url(monkeypatch, tmp_path):
    secret = tmp_path / "postgres_password.txt"
    secret.write_text("p@ss/w%rd\n", encoding="utf-8")
    monkeypatch.setenv("POSTGRES_URL", "postgresql://calltrainer@calltrainer-db:5432/calltrainer")
    monkeypatch.setenv("POSTGRES_PASSWORD_FILE", str(secret))
    url = build_database_url()
    assert url.password == "p@ss/w%rd"
    assert url.host == "calltrainer-db"
