"""FastAPI app: REST endpoints for setup data, WebSocket route for the live session, static frontend."""

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.session_ws import router as session_ws_router
from backend.auth import check_realm, require_user
from backend.clients import tts
from backend.clients.config import DIREKT_URL
from backend.clients.health import check_backends
from backend.logging_config import configure_logging
from backend.personas import PERSONAS
from backend.scenarios import SCENARIOS

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Check the dependencies before the first request, so an unreachable
    backend shows up as a boot-time log line, not a 500 far from its cause.
    The checks only log — a dead dependency does not stop the boot.

    The DiReKT gateway is only reachable from its own network; off it, every
    pipeline call 403s like a credentials problem, so the hint names the real
    cause."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.get(DIREKT_URL)
    except httpx.HTTPError as e:
        logger.error("Could not reach DIREKT_URL (%s): %s — are you on the gateway's network (VPN)?", DIREKT_URL, e)
    await check_backends()
    await tts.prewarm()
    await check_realm()  # mirrors the DiReKT check above, for the Keycloak realm
    yield


app = FastAPI(title="CallTrainer API", lifespan=lifespan)

# For a Vite dev server on :5173 against a host `uvicorn` — not a supported
# workflow (the app runs via Docker, SPA served same-origin), so nothing depends
# on this; kept only to spare a developer who tries it an opaque CORS wall.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(session_ws_router)

FRONTEND_DIST_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")


@app.get("/health")
def health() -> dict[str, str]:
    """Plain health check — open, it's an infrastructure check."""
    return {"status": "ok"}


# The setup lists require a valid Keycloak token (ADR 0009). The static SPA
# mount below stays open so the login screen can load in the first place.
@app.get("/api/personas", dependencies=[Depends(require_user)])
def list_personas() -> list[dict[str, str]]:
    """List personas available for session setup."""
    return [{"id": p.id, "name": p.name, "role": p.role} for p in PERSONAS]


@app.get("/api/scenarios", dependencies=[Depends(require_user)])
def list_scenarios() -> list[dict[str, str]]:
    """List scenarios available for session setup."""
    return [{"id": s.id, "name": s.name, "description": s.description} for s in SCENARIOS]


app.mount("/", StaticFiles(directory=FRONTEND_DIST_DIR, html=True, check_dir=False), name="frontend")
