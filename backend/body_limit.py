"""A ceiling on every request body (ADR 0109).

FastAPI reads a route's declared body before it resolves the login dependency,
so without this anyone could make the backend buffer a body of any size and be
told 401 only afterwards. A declared `Content-Length` over the limit is refused
before a byte is read; a body without one (chunked) is counted as it arrives.
The upload route gets room for its documents, every other route far less than
any JSON it takes.
"""
from __future__ import annotations

from starlette.exceptions import HTTPException
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.documents import MAX_TOTAL_UPLOAD_BYTES

# The longest JSON a route takes is an authored Scenario, a few kB of text.
MAX_BODY_BYTES = 1024 * 1024
# The documents plus the multipart framing around them.
MAX_UPLOAD_BODY_BYTES = MAX_TOTAL_UPLOAD_BYTES + 1024 * 1024
UPLOAD_PATH = "/api/scenarios/document"

_TOO_LARGE = "Die Anfrage ist zu groß."


def limit_for(path: str) -> int:
    """The largest body a request to `path` may carry."""
    return MAX_UPLOAD_BODY_BYTES if path == UPLOAD_PATH else MAX_BODY_BYTES


def _declared_length(scope: Scope) -> int | None:
    for key, value in scope.get("headers", []):
        if key == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


class BodyLimit:
    """ASGI middleware refusing a body over `limit_for(path)` with 413."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = limit_for(scope["path"])
        declared = _declared_length(scope)
        if declared is not None and declared > limit:
            await PlainTextResponse(_TOO_LARGE, status_code=413)(scope, receive, send)
            return

        received = 0

        async def counted() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    # An HTTPException, because FastAPI re-raises that one from
                    # its body parsing (anything else becomes a 400) and
                    # Starlette's exception middleware turns it into the answer.
                    raise HTTPException(413, _TOO_LARGE)
            return message

        await self.app(scope, counted, send)
