"""Centralized logging.

Covers ADR 0039 and ADR 0055: colored per-module console output plus a log
file that is opened fresh once per process and then kept for the whole run
(every Session, not just the current one), carrying the session id on every
line so calls stay separable.
"""

import logging

import pytest

from backend import logging_config
from backend.logging_config import (
    _SessionIdFilter,
    configure_logging,
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
    assert log_file.exists(), "the log file is created (with parents)"


def test_log_file_keeps_lines_across_sessions(tmp_path):
    """The file accumulates for the whole run -- a new Session does not clear
    the previous one's lines (ADR 0055)."""
    log_file = tmp_path / "calltrainer.log"
    logging_config._state.configured = False
    configure_logging(log_file)

    with session_id_scope("session-one"):
        logging.getLogger("backend.test").info("first call noise")
    with session_id_scope("session-two"):
        logging.getLogger("backend.test").info("second call noise")
    for h in logging.getLogger().handlers:
        h.flush()

    contents = log_file.read_text(encoding="utf-8")
    assert "first call noise" in contents, "the earlier Session's lines are still there"
    assert "second call noise" in contents
    assert "[session session-one]" in contents and "[session session-two]" in contents


def test_configure_logging_opens_the_file_fresh_each_process(tmp_path):
    """`w` mode: a restart (a fresh configure_logging) starts the file over,
    which is what bounds its growth (ADR 0055)."""
    log_file = tmp_path / "calltrainer.log"
    log_file.write_text("stale line from a previous run\n", encoding="utf-8")

    logging_config._state.configured = False
    configure_logging(log_file)

    assert "stale line" not in log_file.read_text(encoding="utf-8")
