"""Deep links into the client-side router survive a reload (F-31, ADR 0009).

Plain `StaticFiles` 404s SPA paths like `/profil` on reload. Driven against a directory built
here, not `frontend/dist`, so it needs no Node toolchain or prior build.
"""
import httpx
import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app import SinglePageApp, app

INDEX_HTML = "<!doctype html><title>Calltrainer</title><div id=root></div>"
BUNDLE_JS = "console.log('bundle')"


@pytest.fixture
def spa_client(tmp_path):
    """A bare app serving `SinglePageApp` over a minimal built frontend."""
    (tmp_path / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "index-abc123.js").write_text(BUNDLE_JS, encoding="utf-8")

    bare = FastAPI()

    @bare.get("/api/personas")
    def _personas() -> list[str]:
        return []

    bare.mount("/", SinglePageApp(directory=str(tmp_path), html=True), name="frontend")
    transport = httpx.ASGITransport(app=bare)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


@pytest.mark.parametrize(
    "path",
    ["/profil", "/impressum", "/datenschutz", "/barrierefreiheit", "/hinweise", "/irgendwas"],
)
async def test_a_client_route_is_served_the_app(spa_client, path: str) -> None:
    """Reloading a page the router owns has to return the app, not a 404 --
    otherwise every deep link and every shared URL is broken."""
    async with spa_client as client:
        response = await client.get(path)

    assert response.status_code == 200
    assert response.text == INDEX_HTML


async def test_the_root_still_works(spa_client) -> None:
    """The ordinary entry point must not be affected by the fallback."""
    async with spa_client as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert response.text == INDEX_HTML


async def test_a_real_asset_is_served_as_itself(spa_client) -> None:
    """The fallback only applies where nothing was found; a file that exists
    is served normally, with its own content type."""
    async with spa_client as client:
        response = await client.get("/assets/index-abc123.js")

    assert response.status_code == 200
    assert response.text == BUNDLE_JS


async def test_a_missing_asset_stays_a_404(spa_client) -> None:
    """A mistyped bundle or a missing image must fail as itself. Answering it
    with `index.html` would hand a script tag a page of HTML, and the error
    would surface as an unexplained syntax error instead of a 404."""
    async with spa_client as client:
        response = await client.get("/assets/does-not-exist.js")

    assert response.status_code == 404
    assert "<div id=root>" not in response.text


@pytest.mark.parametrize(
    "path",
    ["/api/unknown", "/api/sessions/nope/deeper", "/ws/nothing", "/health/nothing"],
)
async def test_server_paths_never_fall_back_to_the_app(spa_client, path: str) -> None:
    """An unknown endpoint under a server-owned prefix stays a 404, not an HTML page
    the caller then fails to parse as JSON.
    """
    async with spa_client as client:
        response = await client.get(path)

    assert response.status_code == 404
    assert "<div id=root>" not in response.text


async def test_a_real_api_route_is_unaffected(spa_client) -> None:
    """The mount sits under the API, so a route that exists still answers --
    this is what proves the fallback did not swallow the routing table."""
    async with spa_client as client:
        response = await client.get("/api/personas")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("path", ["/openapi.json", "/docs", "/redoc"])
async def test_the_api_schema_is_not_published(path: str) -> None:
    """FastAPI serves its schema and two documentation pages by default, open
    to anyone and outside the login. Nothing reads them, so the deployed app
    must not hand out every route and payload shape: whatever the path answers
    (the SPA's fallback, or a 404 in a checkout without a built frontend), it
    is not the schema."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(path)

    assert "openapi" not in response.text.lower()
    assert "swagger" not in response.text.lower()


def test_no_cors_middleware() -> None:
    """The SPA is served same-origin, so no origin needs allowing; a leftover
    allow-list is one more thing to reason about on a deployed server."""
    assert all(m.cls is not CORSMiddleware for m in app.user_middleware)
