"""FastAPI app: REST endpoints for setup data, WebSocket route for the live session, static frontend."""

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from backend.api.session_ws import router as session_ws_router
from backend.db import repository
from backend.db.session import session_scope

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("calltrainer")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """EFRE_URL is only reachable via the university network. Without it,
    every call fails with a 403 that looks like a credentials problem."""
    efre_url = os.environ["EFRE_URL"]
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.get(efre_url)
    except httpx.HTTPError as e:
        logger.error("Could not reach EFRE_URL (%s): %s — are you connected to the university network", efre_url, e)
    yield


app = FastAPI(title="CallTrainer API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    # Only relevant for dev server
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
    """List personas available for session setup.

    Sync def on purpose: FastAPI runs these in a threadpool, so the blocking
    database read does not touch the event loop that serves live sessions.
    """
    try:
        with session_scope() as db:
            personas = repository.list_personas(db)
    except SQLAlchemyError as e:
        logger.error("Loading personas failed: %s", e)
        raise HTTPException(status_code=503, detail="Database unavailable") from e
    return [{"id": p.id, "name": p.name, "role": p.role} for p in personas]


@app.get("/api/scenarios")
def list_scenarios() -> list[dict[str, str]]:
    """List scenarios available for session setup. Sync def — see list_personas."""
    try:
        with session_scope() as db:
            scenarios = repository.list_scenarios(db)
    except SQLAlchemyError as e:
        logger.error("Loading scenarios failed: %s", e)
        raise HTTPException(status_code=503, detail="Database unavailable") from e
    return [{"id": s.id, "name": s.name, "description": s.description} for s in scenarios]


app.mount("/", StaticFiles(directory=FRONTEND_DIST_DIR, html=True, check_dir=False), name="frontend")
