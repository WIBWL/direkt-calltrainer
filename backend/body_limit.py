"""A ceiling on every request body (ADR 0109): FastAPI parses a declared body
before resolving the login. A declared length is refused unread; a chunked body
is counted as it arrives."""
from __future__ import annotations

from starlette.exceptions import HTTPException
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.documents import MAX_TOTAL_UPLOAD_BYTES

MAX_BODY_BYTES = 1024 * 1024
MAX_UPLOAD_BODY_BYTES = MAX_TOTAL_UPLOAD_BYTES + 1024 * 1024
UPLOAD_PATH = "/api/scenarios/document"

_TOO_LARGE = "Die Anfrage ist zu groß."


def limit_for(path: str) -> int:
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
                    # HTTPException: FastAPI re-raises it from body parsing (others become 400).
                    raise HTTPException(413, _TOO_LARGE)
            return message

        await self.app(scope, counted, send)
