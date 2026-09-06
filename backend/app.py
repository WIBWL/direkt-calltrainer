"""FastAPI app: REST endpoints for setup data, WebSocket route for the live session, static frontend."""

import asyncio
import contextlib
import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import HTTP_404_NOT_FOUND
from sqlalchemy.exc import SQLAlchemyError

from backend.api.account import router as account_router
from backend.api.consent import router as consent_router
from backend.api.session_ws import router as session_ws_router
from backend.api.sessions import router as sessions_router
from backend.auth import check_realm, require_user
from backend.clients import tts
from backend.clients.config import DIREKT_URL, LOG_TRANSCRIPTS
from backend.clients.health import check_backends
from backend.db.provision import provision
from backend.db.session import session_scope
from backend.logging_config import configure_logging
from backend import library, retention

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
    if LOG_TRANSCRIPTS:
        # Loud, once, at boot. The switch writes what people say aloud into a
        # file that no deletion path reaches (ADR 0066), which is fine while
        # diagnosing a model and not fine in a running pilot — so the one thing
        # it must never be is quiet.
        logger.warning(
            "LOG_TRANSCRIPTS is on: spoken content is being written to the log file. "
            "That log is personal data and is not covered by any deletion path. "
            "Turn it off for anything but local debugging."
        )
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

    Inside the app rather than as a cron entry or a scheduled Redis job. A cron
    entry is a second place to deploy and a second thing to forget; a job queued
    six months ahead does not survive a Redis restart. This asks the database
    what is expired every time it wakes, so a missed run delays a deletion
    rather than cancelling it.

    Every failure is caught and the loop continues. A retention sweep that dies
    on one bad night and never runs again is the failure mode worth designing
    against: nothing would report it, and the period would quietly stop being
    enforced.
    """
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
app.include_router(consent_router)
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


# The setup lists require a valid Keycloak token (ADR 0009). The static SPA
# mount below stays open so the login screen can load in the first place.
@app.get("/api/personas", dependencies=[Depends(require_user)])
def list_personas() -> list[dict[str, str]]:
    """List personas available for session setup.

    Display fields only (ADR 0043) -- the English prompt fields stay on the
    server. The language comes along because it is a property of the Persona and
    not a separate choice, so the card has to say which one it speaks.

    `id` on the wire is the natural key, never the primary key: the client sends
    it straight back in session.start. Retired Personas are filtered out by the
    library -- their rows stay, because stored Sessions reference them.
    """
    return [
        {"id": p.id, "name": p.name, "role": p.role_label, "language": p.language_name}
        for p in library.list_personas()
    ]


@app.get("/api/scenarios", dependencies=[Depends(require_user)])
def list_scenarios() -> list[dict[str, str]]:
    """List scenarios available for session setup.

    Serves the short teaser, not the English call context the model reads, and
    only active rows -- as above.
    """
    return [
        {"id": s.id, "name": s.name, "short_description": s.short_description}
        for s in library.list_scenarios()
    ]


class SinglePageApp(StaticFiles):
    """Static files, with the client-side router's paths falling back to
    `index.html`.

    The SPA owns routes like `/profil` that exist only in the browser. Plain
    `StaticFiles` 404s them, so the app worked until the first reload or shared
    link -- the failure only appears when someone types the URL rather than
    clicking their way to it, which is why it is worth handling here rather
    than noticing it in the pilot.

    Two things deliberately keep their 404. A path under `/api` or `/ws` that
    reaches this mount is an unknown endpoint, and answering it with a page
    would turn a clear 404 into a JSON parse error in the caller. So is any
    path that looks like a file: a mistyped bundle or a missing image must
    fail as itself, not as HTML that a script tag then chokes on.
    """

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
