"""Deep links into the client-side router survive a reload (F-31, ADR 0009).

The SPA owns paths the server has no file for -- `/profil` today, the history
and progress screens next. Plain `StaticFiles` 404s them, which works fine
until someone reloads the page or opens a link, so the failure hides until the
exact moment a user does the ordinary thing.

Driven against a directory this module builds rather than against
`frontend/dist`: the fallback is server behaviour and has to be assertable
without a Node toolchain or a prior `npm run build`, which is also what keeps
this test meaningful in a checkout where the frontend was never built.
"""
import httpx
import pytest
from fastapi import FastAPI

from backend.app import SinglePageApp

INDEX_HTML = "<!doctype html><title>Calltrainer</title><div id=root></div>"
BUNDLE_JS = "console.log('bundle')"


@pytest.fixture
def spa_client(tmp_path):
    """A bare app serving `SinglePageApp` over a minimal built frontend."""
    (tmp_path / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "index-abc123.js").write_text(BUNDLE_JS, encoding="utf-8")

    app = FastAPI()

    @app.get("/api/personas")
    def _personas() -> list[str]:
        return []

    app.mount("/", SinglePageApp(directory=str(tmp_path), html=True), name="frontend")
    transport = httpx.ASGITransport(app=app)
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
    """An unknown endpoint under a server-owned prefix stays a 404.

    Answering with a page would turn a clear failure into a JSON parse error
    in the caller, which is a much worse thing to debug than the 404 it
    replaced.
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
