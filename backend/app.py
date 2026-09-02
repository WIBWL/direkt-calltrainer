"""FastAPI app: REST endpoints for setup data, WebSocket route for the live session, static frontend."""

import asyncio
import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.api.session_ws import router as session_ws_router
from backend.api.sessions import router as sessions_router
from backend.auth import check_realm, require_user
from backend.clients import tts
from backend.clients.config import DIREKT_URL
from backend.clients.health import check_backends
from backend.db import models as db_models
from backend.db.provision import provision
from backend.db.session import session_scope
from backend.logging_config import configure_logging

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
    # Off the event loop: Alembic and the ORM are both synchronous.
    await asyncio.to_thread(_provision_database)
    yield


def _provision_database() -> None:
    """Migrate and seed on startup, so a fresh `docker compose up` is usable.

    Non-fatal, like the backend check above: without it every Session fails to
    persist and silently loses its Feedback, but the call itself still works,
    so a database problem must not stop the app from booting.
    """
    try:
        logger.info("Database provisioned, reference rows created: %s", provision())
    except Exception:
        logger.exception("Database provisioning failed - Sessions will not be persisted")


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
app.include_router(sessions_router)

FRONTEND_DIST_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness: the process is up — open, it's an infrastructure check.

    Deliberately touches nothing else, so a restart loop cannot be caused by a
    dependency being briefly unavailable.
    """
    return {"status": "ok"}


@app.get("/health/ready")
def readiness() -> dict[str, str]:
    """Readiness: the app can actually serve. Separate from liveness because
    every endpoint below needs the database — an instance that answers "ok"
    while Postgres is unreachable would keep receiving traffic it can only
    answer with 503. This is the check compose.yaml asks."""
    try:
        with session_scope() as db:
            db.execute(text("SELECT 1"))
    except SQLAlchemyError as e:
        logger.error("Readiness check failed: %s", e)
        raise HTTPException(status_code=503, detail="Database unavailable") from e
    return {"status": "ready"}


# The setup lists require a valid Keycloak token (ADR 0009). The static SPA
# mount below stays open so the login screen can load in the first place.
@app.get("/api/personas", dependencies=[Depends(require_user)])
def list_personas() -> list[dict[str, str]]:
    """List personas available for session setup.

    Read from the persona table, not from backend/personas.py (ADR 0041): that
    module only seeds it, and ADR 0024 has Users authoring their own Personas,
    which have to live in the table. `id` on the wire is the natural key, never
    the primary key — the client sends it straight back in session.start.

    Only active rows: a retired Persona stays in the table because stored
    Sessions reference it, but it must not be offered for a new call.
    """
    with session_scope() as db:
        rows = (
            db.query(db_models.Persona)
            .filter_by(active=True)
            .order_by(db_models.Persona.persona_id)
            .all()
        )
        return [{"id": p.key, "name": p.name, "role": p.role} for p in rows]


@app.get("/api/scenarios", dependencies=[Depends(require_user)])
def list_scenarios() -> list[dict[str, str]]:
    """List scenarios available for session setup. From the table, as above."""
    with session_scope() as db:
        rows = (
            db.query(db_models.Scenario)
            .filter_by(active=True)
            .order_by(db_models.Scenario.scenario_id)
            .all()
        )
        return [{"id": s.key, "name": s.title, "description": s.description} for s in rows]


app.mount("/", StaticFiles(directory=FRONTEND_DIST_DIR, html=True, check_dir=False), name="frontend")
