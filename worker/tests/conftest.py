"""The worker suite's fixtures. The end-to-end wrap-up tests store a Session
through the backend's write path and read the result back through its API, so
they borrow the backend suite's auth override and client; the environment and
the databases come from `shared/tests/fixtures.py`."""

# pylint: disable=wrong-import-position,unused-import
import pytest

# Imported first as well as registered: pytest registers `pytest_plugins` only
# after this module has run, and the backend import below reads the environment
# the fixtures module sets.
pytest.register_assert_rewrite("shared.tests.fixtures")
import shared.tests.fixtures  # noqa: E402,F401

pytest_plugins = ["shared.tests.fixtures"]

from backend.tests.conftest import _override_auth, api_client  # noqa: E402,F401
