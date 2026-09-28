"""Centralized logging (ADR 0039, ADR 0105).

One handler on stdout, no file: JSON lines for the log shipper, or the colored
lines for a terminal, with the session id on every line either way.
"""

import io
import json
import logging

import pytest

from shared import logging_config
from shared.logging_config import _SessionIdFilter, configure_logging, session_id_scope

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
    try:
        yield
    finally:
        for h in root.handlers[:]:
            if h not in saved_handlers:
                h.close()
        root.handlers[:] = saved_handlers
        logging_config._state.configured = saved_configured


def _configure(monkeypatch, log_format):
    """Run configure_logging() afresh with `log_format`, its output captured."""
    monkeypatch.setenv("LOG_FORMAT", log_format)
    logging_config._state.configured = False
    configure_logging()
    stream = io.StringIO()
    (handler,) = logging.getLogger().handlers
    handler.setStream(stream)
    return stream


def test_session_id_scope_tags_records_and_resets():
    assert _tagged_session_id() == "-"  # nothing set outside a session

    with session_id_scope("abc-123"):
        assert _tagged_session_id() == "abc-123"

    assert _tagged_session_id() == "-"  # restored after the block


@pytest.mark.parametrize("log_format", ["json", "pretty"])
def test_configure_logging_installs_one_stream_handler_and_no_file(monkeypatch, log_format):
    _configure(monkeypatch, log_format)

    (handler,) = logging.getLogger().handlers
    assert type(handler) is logging.StreamHandler  # pylint: disable=unidiomatic-typecheck


def test_json_lines_carry_the_session_as_a_field(monkeypatch):
    stream = _configure(monkeypatch, "json")

    with session_id_scope("session-one"):
        logging.getLogger("backend.test").info("first call %s", "noise")
    logging.getLogger("backend.test").warning("between calls")

    first, second = (json.loads(line) for line in stream.getvalue().splitlines())
    assert first["session"] == "session-one"
    assert first["message"] == "first call noise"
    assert first["level"] == "INFO" and first["logger"] == "backend.test"
    assert second["session"] == "-"


def test_json_keeps_the_traceback_inside_the_one_line(monkeypatch):
    """A multi-line traceback as its own lines would reach the log shipper as
    that many separate entries, none of them saying which error it belongs to."""
    stream = _configure(monkeypatch, "json")

    try:
        raise ValueError("boom")
    except ValueError:
        logging.getLogger("backend.test").exception("failed")

    (line,) = stream.getvalue().splitlines()
    assert "ValueError: boom" in json.loads(line)["exception"]


def test_pretty_lines_carry_the_session_in_brackets(monkeypatch):
    stream = _configure(monkeypatch, "pretty")

    with session_id_scope("session-two"):
        logging.getLogger("backend.test").info("second call noise")

    assert "[session session-two]" in stream.getvalue()
    assert "second call noise" in stream.getvalue()


@pytest.mark.parametrize("log_format", ["", "text"])
def test_an_unset_or_unknown_format_refuses_to_start(monkeypatch, log_format):
    monkeypatch.setenv("LOG_FORMAT", log_format)
    logging_config._state.configured = False

    with pytest.raises(RuntimeError, match="LOG_FORMAT"):
        configure_logging()
