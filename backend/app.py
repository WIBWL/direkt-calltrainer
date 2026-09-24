"""FastAPI app: REST endpoints for setup data, WebSocket route for the live session, static frontend."""

import asyncio
import contextlib
import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import HTTP_404_NOT_FOUND

from backend.api.account import router as account_router
from backend.api.consent import router as consent_router
from backend.api.focus import router as focus_router
from backend.api.personas import router as personas_router
from backend.api.scenarios import router as scenarios_router
from backend.api.session_ws import router as session_ws_router
from backend.api.sessions import router as sessions_router
from backend.api.tenant import router as tenant_router
from backend.auth import check_realm
from backend.clients import tts
from backend.clients.config import DIREKT_URL
from backend.clients.health import check_backends
from backend.db.provision import provision
from backend.db.session import session_scope
from backend.logging_config import configure_logging
from backend import retention

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Check the dependencies before the first request, so a dead one is a boot-time
    log line rather than a 500 far from its cause. The checks only log.

    Off the DiReKT gateway's network every pipeline call 403s like a credentials
    problem, so the hint names the real cause."""
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

    sweeper = asyncio.create_task(_retention_loop())
    try:
        yield
    finally:
        sweeper.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await sweeper


# How often the retention sweep runs. Daily is far more often than needed for a
# six-month period; the point is that a missed run is harmless, so the interval
# only has to be short enough that nothing lingers noticeably past its date.
_SWEEP_INTERVAL_S = 24 * 60 * 60


async def _retention_loop() -> None:
    """Delete expired Sessions, once at startup and daily after that (ADR 0067).

    In-process rather than cron or a scheduled Redis job (which would not survive a
    Redis restart); it asks the database each time, so a missed run only delays.
    Every failure is caught: a sweep that dies silently stops enforcing the period."""
    while True:
        try:
            removed = await asyncio.to_thread(retention.sweep_now)
            if removed:
                logger.info("Retention sweep removed %d expired session(s)", removed)
        except Exception:  # pylint: disable=broad-except
            # CancelledError is not caught here: since Python 3.8 it derives
            # from BaseException, so cancelling the task at shutdown passes
            # straight through rather than being logged as a sweep failure.
            logger.exception("Retention sweep failed; retrying at the next interval")
        await asyncio.sleep(_SWEEP_INTERVAL_S)


def _provision_database() -> None:
    """Migrate and seed on startup, so a fresh `docker compose up` is usable.

    Non-fatal: without it Sessions are not persisted, but calls still work.
    """
    try:
        logger.info("Database provisioned, reference rows created: %s", provision())
    except Exception:  # pylint: disable=broad-exception-caught
        # Any provisioning failure is non-fatal on purpose (see the docstring).
        logger.exception("Database provisioning failed - Sessions will not be persisted")


# No API docs or published schema (`/docs`, `/redoc`, `/openapi.json` would expose
# every route without a login); the SPA's wire types live in frontend/src/protocol.ts.
# No CORS middleware: the SPA is served from the same origin as the API.
app = FastAPI(
    title="CallTrainer API",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.include_router(personas_router)
app.include_router(scenarios_router)
app.include_router(tenant_router)
app.include_router(session_ws_router)
app.include_router(sessions_router)
app.include_router(consent_router)
app.include_router(focus_router)
app.include_router(account_router)

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


# The setup lists (backend/api/personas.py, scenarios.py) require a valid
# Keycloak token (ADR 0009). The static SPA mount below stays open so the login
# screen can load in the first place.


class SinglePageApp(StaticFiles):
    """Static files, with the client-side router's paths falling back to
    `index.html`, so a reload or shared link to e.g. `/profil` works.

    Deliberately still 404: paths under `/api`, `/ws`, `/health` (an unknown
    endpoint must not answer with HTML) and anything that looks like a file."""

    # Reserved for the API and the live session; never the SPA's to route.
    _SERVER_PREFIXES = ("/api", "/ws", "/health")

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as e:
            # StaticFiles signals "no such file" by raising, not by returning a
            # 404 response -- so this has to be caught rather than inspected.
            # Anything that is not a 404 (a 405, a path escaping the root) is
            # not ours to reinterpret.
            if e.status_code != HTTP_404_NOT_FOUND or not self._is_client_route(path):
                raise
        return await super().get_response("index.html", scope)

    def _is_client_route(self, path: str) -> bool:
        """True where a 404 should be answered with the app instead."""
        # The mount strips its own prefix, so `path` arrives relative.
        request_path = "/" + path.lstrip("/")
        if request_path.startswith(self._SERVER_PREFIXES):
            return False
        # A dot in the last segment means the caller asked for a file, not a
        # route -- "/profil" falls back, "/assets/main.js" stays a 404.
        return "." not in request_path.rsplit("/", 1)[-1]


app.mount("/", SinglePageApp(directory=FRONTEND_DIST_DIR, html=True, check_dir=False), name="frontend")
