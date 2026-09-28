"""Cross-origin access for the SPA (ADR 0107).

In a deployment the SPA and the API are two hosts, so the browser asks before
every authorised request. `CORS_ORIGINS` names the origins it may come from,
comma-separated, or `*`; unset registers nothing at all, which is the
development setup, where Vite proxies the API onto the SPA's own origin.

Tokens travel in the `Authorization` header, never in a cookie, so credentials
stay off. The call's WebSocket gets no preflight from a browser and needs none:
its token is in the first message, which a foreign page cannot supply.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.env import optional


def origins() -> list[str]:
    """The allowed origins, or none when `CORS_ORIGINS` is unset."""
    value = optional("CORS_ORIGINS") or ""
    return [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]


def install(app: FastAPI) -> None:
    """Register the middleware if any origin is allowed."""
    allowed = origins()
    if not allowed:
        return
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type"],
        # The data export names its file there (DataOverview.tsx reads it).
        expose_headers=["Content-Disposition"],
        # A preflight answer may be reused for ten minutes, not re-asked per request.
        max_age=600,
    )
