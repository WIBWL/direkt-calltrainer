"""The one place a setting is read: every setting is required, and any can come
from the file named by `NAME_FILE` (ADR 0106)."""

import os
from pathlib import Path


def _read(name: str) -> str | None:
    """The value of `name` or of `name_FILE`, refusing both at once."""
    value = os.environ.get(name) or None
    path = os.environ.get(f"{name}_FILE") or None
    if value is not None and path is not None:
        raise RuntimeError(f"{name} and {name}_FILE are both set; set one")
    if path is not None:
        try:
            return Path(path).read_text(encoding="utf-8").strip() or None
        except OSError as exc:
            raise RuntimeError(f"{name}_FILE names {path}, which cannot be read: {exc}") from exc
    return value


def required(name: str) -> str:
    value = _read(name)
    if value is None:
        raise RuntimeError(f"{name} is required (see .env.example)")
    return value


def optional(name: str) -> str | None:
    """A setting whose absence means something (e.g. no CORS), not a fallback."""
    return _read(name)
