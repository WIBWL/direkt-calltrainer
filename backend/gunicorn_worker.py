"""The gunicorn worker class the backend image runs (the Dockerfile's CMD).

uvicorn's own, with the WebSocket frame ceiling lowered from its 16 MB default
to `WS_MAX_FRAME_BYTES` (ADR 0109): the first frame arrives before anybody is
authenticated, and one turn's audio needs far less. gunicorn cannot pass that
setting on the command line, hence a class. Locally, `uvicorn --reload` keeps
the default; the per-turn cap in `session_ws.py` holds either way.
"""
from uvicorn_worker import UvicornWorker

from backend.limits import WS_MAX_FRAME_BYTES


class Worker(UvicornWorker):  # pylint: disable=too-few-public-methods  # a config holder
    """`UvicornWorker` with a lower WebSocket frame ceiling."""

    CONFIG_KWARGS = {**UvicornWorker.CONFIG_KWARGS, "ws_max_size": WS_MAX_FRAME_BYTES}
