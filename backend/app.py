"""The FastAPI app."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from shared.clients.config import DIREKT_URL
from shared.db.session import session_scope
from shared.logging_config import configure_logging
from backend.api.account import router as account_router
from backend.api.consent import router as consent_router
from backend.api.focus import router as focus_router
from backend.api.personas import router as personas_router
from backend.api.scenarios import router as scenarios_router
from backend.api.session_ws import router as session_ws_router
from backend.api.sessions import router as sessions_router
from backend.api.tenant import router as tenant_router
from backend.auth import check_realm
from backend.body_limit import BodyLimit
from backend.clients import tts
from backend.clients.health import check_backends
from backend.db.provision import provision
from backend import cors, retention

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Boot checks only log. Off the gateway's network every call 403s like a
    credentials problem, hence the VPN hint."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.get(DIREKT_URL)
    except httpx.HTTPError as e:
        logger.error("Could not reach DIREKT_URL (%s): %s — are you on the gateway's network (VPN)?", DIREKT_URL, e)
    await check_backends()
    await tts.prewarm()
    await check_realm()
    await asyncio.to_thread(_provision_database)

    sweeper = asyncio.create_task(_retention_loop())
    try:
        yield
    finally:
        sweeper.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await sweeper


# A missed run is harmless; daily just keeps nothing lingering past its date.
_SWEEP_INTERVAL_S = 24 * 60 * 60


async def _retention_loop() -> None:
    """At startup and daily (ADR 0067). Every failure is caught, so the loop never dies."""
    while True:
        try:
            removed = await asyncio.to_thread(retention.sweep_now)
            if removed:
                logger.info("Retention sweep removed %d expired session(s)", removed)
        except Exception:  # pylint: disable=broad-except
            # CancelledError is a BaseException, so shutdown passes straight through.
            logger.exception("Retention sweep failed; retrying at the next interval")
        await asyncio.sleep(_SWEEP_INTERVAL_S)


def _provision_database() -> None:
    """Non-fatal: without it Sessions are not persisted, but calls still work."""
    try:
        logger.info("Database provisioned, reference rows created: %s", provision())
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Database provisioning failed - Sessions will not be persisted")


# No /docs, /redoc or /openapi.json: they would publish every route without a login.
app = FastAPI(
    title="CallTrainer API",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
# Before CORS, so CORS wraps it: a 413 without CORS headers reads as a network error.
app.add_middleware(BodyLimit)
cors.install(app)

app.include_router(personas_router)
app.include_router(scenarios_router)
app.include_router(tenant_router)
app.include_router(session_ws_router)
app.include_router(sessions_router)
app.include_router(consent_router)
app.include_router(focus_router)
app.include_router(account_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness only; touches nothing, so a dependency blip cannot cause a restart loop."""
    return {"status": "ok"}


@app.get("/health/ready")
def readiness() -> dict[str, str]:
    """Readiness: the database answers."""
    try:
        with session_scope() as db:
            db.execute(text("SELECT 1"))
    except SQLAlchemyError as e:
        logger.error("Readiness check failed: %s", e)
        raise HTTPException(status_code=503, detail="Database unavailable") from e
    return {"status": "ready"}
