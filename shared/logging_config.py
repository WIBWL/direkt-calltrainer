"""Central logging setup: one handler on stdout, stamping every line with its
Session (ADR 0039, ADR 0105). Call `configure_logging()` once at startup.

`LOG_FORMAT` picks the shape: `json`, one object per line for the log shipper
that reads the containers' output (the images set it), or `pretty`, the colored
lines for a developer's terminal (`.env.example` sets it). There is no log file.
"""

import contextlib
import contextvars
import json
import logging
from datetime import UTC, datetime

from shared.env import required

# Set once per WebSocket connection (see backend/api/session_ws.py) and read
# by _SessionIdFilter below; propagates through every awaited call in that
# connection's task tree, including into third-party libraries like httpx.
session_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("session_id", default=None)

_LOG_FORMAT = "%(asctime)s [%(levelname)s] [session %(session_id)s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_LEVEL_COLORS = {
    logging.WARNING: "\x1b[33m",  # yellow
    logging.ERROR: "\x1b[31m",  # red
    logging.CRITICAL: "\x1b[1;31m",  # bold red
}
# One color per pipeline stage so they're visually distinguishable at a
# glance; severity colors above still take priority over these.
_LOGGER_COLORS = {
    "backend.api.session_ws": "\x1b[34m",  # blue
    "backend.session.orchestrator": "\x1b[32m",  # green
    "shared.clients.llm": "\x1b[35m",  # magenta
    "backend.clients.stt": "\x1b[36m",  # cyan
    "backend.clients.tts": "\x1b[97m",  # bright white
    "backend.clients.health": "\x1b[90m",  # gray
}
_DIM = "\x1b[2m"
_RESET = "\x1b[0m"


@contextlib.contextmanager
def session_id_scope(session_id: str):
    """Tags every log line emitted inside the block with this Session's id."""
    token = session_id_var.set(session_id)
    try:
        yield
    finally:
        session_id_var.reset(token)


class _SessionIdFilter(logging.Filter):
    """Adds the current Session's id (session_id_var) to every record, "-"
    if none is set (e.g. startup logs, before any call has connected)."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.session_id = session_id_var.get() or "-"
        return True


class _ColorFormatter(logging.Formatter):
    """Colors warnings/errors regardless of source; dims what third-party
    libraries still emit (alembic, kugelaudio, ...) so our own lines stand
    out. httpx is quieted outright in configure_logging()."""

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        color = _LEVEL_COLORS.get(record.levelno) or _LOGGER_COLORS.get(record.name)
        if color is None and not record.name.startswith(("backend", "shared", "worker")):
            color = _DIM
        return f"{color}{message}{_RESET}" if color else message


class _JsonFormatter(logging.Formatter):
    """One JSON object per line, the Session id a field of its own, so a query
    can select one call's lines without parsing the message."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "session": record.__dict__.get("session_id", "-"),
            "message": record.getMessage(),
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


_FORMATTERS = {
    "json": _JsonFormatter,
    "pretty": lambda: _ColorFormatter(_LOG_FORMAT, _DATE_FORMAT),
}


class _State:
    """Holds configure_logging()'s setup state -- a mutable attribute on a
    shared instance instead of module globals reassigned via `global`."""

    configured = False


_state = _State()


def configure_logging() -> None:
    """Sets up the one stdout handler on the root logger, in the `LOG_FORMAT`
    shape; safe to call more than once (later calls are a no-op).

    Replaces any existing root handlers (e.g. gunicorn's own), so this is the
    only thing writing our output."""
    if _state.configured:
        return
    log_format = required("LOG_FORMAT")
    if log_format not in _FORMATTERS:
        raise RuntimeError(f"LOG_FORMAT must be one of {', '.join(_FORMATTERS)}, not {log_format!r}")
    _state.configured = True

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)

    # httpx logs a line for every request it makes at INFO -- the startup
    # backend checks, every OIDC key refresh, every pipeline call. Our own
    # clients (shared/clients/*, backend/clients/*) already log the calls that
    # matter, so drop httpx to WARNING; raise it back if you need raw HTTP tracing.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    console = logging.StreamHandler()
    console.setFormatter(_FORMATTERS[log_format]())
    console.addFilter(_SessionIdFilter())
    root.addHandler(console)
