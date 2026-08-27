"""Central logging setup: colored console + file, both showing which
Session a line belongs to. Call configure_logging() once at startup."""

import contextlib
import contextvars
import logging
from pathlib import Path

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
    "backend.clients.llm": "\x1b[35m",  # magenta
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
    """Colors warnings/errors regardless of source; dims third-party noise
    (e.g. httpx's own request logs) so our own lines stand out."""

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        color = _LEVEL_COLORS.get(record.levelno) or _LOGGER_COLORS.get(record.name)
        if color is None and not record.name.startswith("backend"):
            color = _DIM
        return f"{color}{message}{_RESET}" if color else message


class _State:
    """Holds configure_logging()'s setup state -- a mutable attribute on a
    shared instance instead of module globals reassigned via `global`."""

    configured = False
    file_handler: logging.FileHandler | None = None


_state = _State()


def configure_logging(log_file: str | Path = "logs/calltrainer.log") -> None:
    """Sets up console (colored) and file (plain) handlers on the root
    logger; safe to call more than once (later calls are a no-op).

    Replaces any handlers already on the root logger (e.g. gunicorn's own
    default "console" handler, installed on the root logger before this
    module is even imported) so this is the only thing writing our output.
    """
    if _state.configured:
        return
    _state.configured = True

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)
    session_filter = _SessionIdFilter()

    console = logging.StreamHandler()
    console.setFormatter(_ColorFormatter(_LOG_FORMAT, _DATE_FORMAT))
    console.addFilter(session_filter)
    root.addHandler(console)

    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    _state.file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    _state.file_handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
    _state.file_handler.addFilter(session_filter)
    root.addHandler(_state.file_handler)


def reset_session_log() -> None:
    """Truncates the log file so it only ever holds the current/last
    conversation, called when a new Session starts (see session_ws.py)."""
    handler = _state.file_handler
    if handler is None:
        return
    handler.acquire()
    try:
        handler.stream.seek(0)
        handler.stream.truncate()
    finally:
        handler.release()
