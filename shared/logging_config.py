"""One stdout handler, `json` or `pretty` by `LOG_FORMAT`, stamping each line
with its Session (ADR 0105)."""

import contextlib
import contextvars
import json
import logging
from datetime import UTC, datetime

from shared.env import required

# Set per WebSocket connection; follows the connection's whole task tree.
session_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("session_id", default=None)

_LOG_FORMAT = "%(asctime)s [%(levelname)s] [session %(session_id)s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_LEVEL_COLORS = {
    logging.WARNING: "\x1b[33m",  # yellow
    logging.ERROR: "\x1b[31m",  # red
    logging.CRITICAL: "\x1b[1;31m",  # bold red
}
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
    token = session_id_var.set(session_id)
    try:
        yield
    finally:
        session_id_var.reset(token)


class _SessionIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.session_id = session_id_var.get() or "-"
        return True


class _ColorFormatter(logging.Formatter):
    """Colours by severity or stage, and dims third-party lines."""

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        color = _LEVEL_COLORS.get(record.levelno) or _LOGGER_COLORS.get(record.name)
        if color is None and not record.name.startswith(("backend", "shared", "worker")):
            color = _DIM
        return f"{color}{message}{_RESET}" if color else message


class _JsonFormatter(logging.Formatter):
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
    configured = False


_state = _State()


def configure_logging() -> None:
    """Idempotent. Replaces any existing root handlers, gunicorn's included."""
    if _state.configured:
        return
    log_format = required("LOG_FORMAT")
    if log_format not in _FORMATTERS:
        raise RuntimeError(f"LOG_FORMAT must be one of {', '.join(_FORMATTERS)}, not {log_format!r}")
    _state.configured = True

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)

    # httpx logs every request at INFO; our clients log the ones that matter.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    console = logging.StreamHandler()
    console.setFormatter(_FORMATTERS[log_format]())
    console.addFilter(_SessionIdFilter())
    root.addHandler(console)
