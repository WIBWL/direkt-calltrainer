"""Centralized logging.

Covers ADR 0039: colored per-module console output plus a per-session log
file that is truncated at the start of each new session and carries the
session id on every line.
"""

import logging

import pytest

from backend import logging_config
from backend.logging_config import (
    _SessionIdFilter,
    configure_logging,
    reset_session_log,
    session_id_scope,
)

# _state is the module's deliberate singleton; these tests drive it on purpose.
# pylint: disable=missing-function-docstring,protected-access


def _tagged_session_id():
    """Run the session-id filter over a fresh record and return the tag it set."""
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "msg", None, None)
    _SessionIdFilter().filter(record)
    return record.__dict__["session_id"]


@pytest.fixture(autouse=True)
def _restore_logging():
    """Each test here rewires the root logger; put it back afterwards so it
    doesn't leak into other test modules."""
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_configured = logging_config._state.configured
    saved_file_handler = logging_config._state.file_handler
    try:
        yield
    finally:
        for h in root.handlers[:]:
            if h not in saved_handlers:
                h.close()
        root.handlers[:] = saved_handlers
        logging_config._state.configured = saved_configured
        logging_config._state.file_handler = saved_file_handler


def test_session_id_scope_tags_records_and_resets():
    assert _tagged_session_id() == "-"  # nothing set outside a session

    with session_id_scope("abc-123"):
        assert _tagged_session_id() == "abc-123"

    assert _tagged_session_id() == "-"  # restored after the block


def test_configure_logging_installs_console_and_file_handlers(tmp_path):
    log_file = tmp_path / "sub" / "calltrainer.log"
    # configure_logging is a one-shot guarded by module state; force a re-run.
    logging_config._state.configured = False
    configure_logging(log_file)

    root = logging.getLogger()
    handler_types = {type(h).__name__ for h in root.handlers}
    assert "StreamHandler" in handler_types
    assert "FileHandler" in handler_types
    assert log_file.exists(), "the per-session log file is created (with parents)"


def test_reset_session_log_truncates_the_file(tmp_path):
    log_file = tmp_path / "calltrainer.log"
    logging_config._state.configured = False
    configure_logging(log_file)

    logging.getLogger("backend.test").info("first session noise")
    for h in logging.getLogger().handlers:
        h.flush()
    assert log_file.read_text(encoding="utf-8").strip() != ""

    reset_session_log()
    assert log_file.read_text(encoding="utf-8") == "", "a new session starts from an empty log"
