"""The backend image's gunicorn worker: uvicorn's, with the WebSocket frame
ceiling lowered (ADR 0109); gunicorn cannot pass it on the command line."""
from uvicorn_worker import UvicornWorker

from backend.limits import WS_MAX_FRAME_BYTES


class Worker(UvicornWorker):  # pylint: disable=too-few-public-methods  # a config holder
    CONFIG_KWARGS = {**UvicornWorker.CONFIG_KWARGS, "ws_max_size": WS_MAX_FRAME_BYTES}
