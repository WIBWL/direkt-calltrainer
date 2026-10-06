"""CORS for the SPA's host only, and none when unset (ADR 0107)."""

import httpx
import pytest
from fastapi import FastAPI

from backend import cors

# pylint: disable=missing-function-docstring

SPA = "https://calltrainer.efre-direkt.de"


def _app(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
    else:
        monkeypatch.setenv("CORS_ORIGINS", value)
    app = FastAPI()

    @app.get("/api/ping")
    def ping():
        return {"ok": True}

    cors.install(app)
    return app


async def _preflight(app, origin):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        return await client.options("/api/ping", headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        })


def test_the_origins_are_split_and_trimmed(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", f" {SPA}/ , http://localhost:5173")
    assert cors.origins() == [SPA, "http://localhost:5173"]


@pytest.mark.parametrize("value", [None, ""])
def test_unset_installs_nothing(monkeypatch, value):
    app = _app(monkeypatch, value)
    assert not [m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware"]


async def test_the_spa_may_send_its_token(monkeypatch):
    response = await _preflight(_app(monkeypatch, SPA), SPA)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == SPA
    assert "authorization" in response.headers["access-control-allow-headers"].lower()


async def test_another_origin_is_refused(monkeypatch):
    response = await _preflight(_app(monkeypatch, SPA), "https://evil.example")
    assert "access-control-allow-origin" not in response.headers


async def test_the_export_filename_is_readable(monkeypatch):
    app = _app(monkeypatch, SPA)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/ping", headers={"Origin": SPA})
    assert "content-disposition" in response.headers["access-control-expose-headers"].lower()
