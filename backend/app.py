"""FastAPI app: REST endpoints for setup data, WebSocket route for the live Session, static frontend."""

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.session_ws import router as session_ws_router
from backend.languages import LANGUAGES
from backend.personas import PERSONAS
from backend.scenarios import SCENARIOS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("calltrainer")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """EFRE-Direkt is only reachable via the university VPN. Without it,
    every single STT/LLM/TTS call fails with a 403 that looks like a
    credentials problem, easy to miss buried in per-request logs, and (before
    this check existed) triggered a reconnect loop on the frontend since each
    failed opening Turn immediately re-triggered a fresh pre-warm attempt.
    This logs one clear, actionable error right at startup instead — a
    non-2xx response still means the host was reached (VPN is fine, there's
    just no handler at "/"), so only an actual connection failure counts."""
    efre_url = os.environ["EFRE_URL"]
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.get(efre_url)
    except httpx.HTTPError as e:
        logger.error("Could not reach EFRE_URL (%s): %s — are you connected to the university VPN?", efre_url, e)
    yield


app = FastAPI(title="CallTrainer API", lifespan=lifespan)

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
    """Plain health check."""
    return {"status": "ok"}


@app.get("/api/personas")
def list_personas() -> list[dict[str, str]]:
    """List Personas available for Session setup."""
    return [
        {"id": p.id, "name": p.name, "training_goal": p.training_goal}
        for p in PERSONAS.values()
    ]


@app.get("/api/languages")
def list_languages() -> list[dict[str, str]]:
    """List Languages available for Session setup."""
    return [{"id": id_, "name": name} for id_, name in LANGUAGES.items()]


@app.get("/api/scenarios")
def list_scenarios() -> list[dict[str, str]]:
    """List Scenarios available for Session setup."""
    return [{"id": s.id, "name": s.name, "description": s.description} for s in SCENARIOS.values()]


app.mount("/", StaticFiles(directory=FRONTEND_DIST_DIR, html=True, check_dir=False), name="frontend")
