"""The one place a setting is read from the environment.

Every setting is required: there are no defaults in the code. A fallback that
happens to look right only moves the failure from boot to the first request --
`.env.example` is where the development values live, and a deployment names
every one of them.

Any setting can instead come from a file, named by the same variable with a
`_FILE` suffix (`DIREKT_API_KEY_FILE=/run/secrets/...`). That is how a
deployment hands over its secrets: as Docker secrets, which never show up in
`docker inspect` or in the environment of a process that did not ask for them.
"""

import os
from pathlib import Path


def _read(name: str) -> str | None:
    """The value of `name` or of `name_FILE`, or None if neither is set.

    Refuses both at once: which of the two would win is a guess, and the two can
    disagree without anything noticing."""
    value = os.environ.get(name) or None
    path = os.environ.get(f"{name}_FILE") or None
    if value is not None and path is not None:
        raise RuntimeError(f"{name} and {name}_FILE are both set; set one")
    if path is not None:
        try:
            # Stripped: a secret file written by `echo` or an editor ends in a newline.
            return Path(path).read_text(encoding="utf-8").strip() or None
        except OSError as exc:
            raise RuntimeError(f"{name}_FILE names {path}, which cannot be read: {exc}") from exc
    return value


def required(name: str) -> str:
    """A setting that must be set, directly or through `name_FILE`, or throw."""
    value = _read(name)
    if value is None:
        raise RuntimeError(f"{name} is required (see .env.example)")
    return value


def optional(name: str) -> str | None:
    """A setting whose absence means something (e.g. no CORS at all), not a
    fallback value. Read the same way, `_FILE` included."""
    return _read(name)
