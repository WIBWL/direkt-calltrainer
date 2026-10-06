"""Worker fixtures, borrowing the backend's write path, auth override and client."""

# pylint: disable=wrong-import-position,unused-import
import pytest

# Imported first as well as registered: the backend import reads the environment
# the fixtures set.
pytest.register_assert_rewrite("shared.tests.fixtures")
import shared.tests.fixtures  # noqa: E402,F401

pytest_plugins = ["shared.tests.fixtures"]

from backend.tests.conftest import _override_auth, api_client  # noqa: E402,F401
