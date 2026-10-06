"""CORS for the SPA's host (ADR 0107). Unset `CORS_ORIGINS` installs nothing.
Tokens travel in a header, so credentials stay off."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.env import optional


def origins() -> list[str]:
    value = optional("CORS_ORIGINS") or ""
    return [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]


def install(app: FastAPI) -> None:
    allowed = origins()
    if not allowed:
        return
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["Content-Disposition"],
        max_age=600,
    )
