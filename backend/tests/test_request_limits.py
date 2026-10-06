"""Per-account caps and the body ceiling (ADR 0109)."""

import httpx
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from backend import auth, body_limit, limits
from backend.app import app

# pylint: disable=missing-function-docstring,redefined-outer-name


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_call_slots_refuse_past_the_cap_and_free_on_release():
    slots = limits.CallSlots(2)
    assert slots.claim("alice") and slots.claim("alice")
    assert not slots.claim("alice")
    assert slots.claim("bob"), "the cap is per account"
    slots.release("alice")
    assert slots.claim("alice")


def test_a_rate_limit_counts_per_account_within_its_window():
    clock = _Clock()
    limit = limits.RateLimit(2, 60, clock=clock)
    assert limit.allow("alice") and limit.allow("alice")
    assert not limit.allow("alice")
    assert limit.allow("bob")
    clock.now += 61
    assert limit.allow("alice"), "uses older than the window no longer count"


def test_a_refused_use_is_not_counted():
    clock = _Clock()
    limit = limits.RateLimit(1, 60, clock=clock)
    assert limit.allow("alice")
    clock.now += 30
    assert not limit.allow("alice")
    clock.now += 31
    assert limit.allow("alice")


def test_enforce_answers_429_in_german():
    with pytest.raises(HTTPException) as e:
        limits.enforce(limits.RateLimit(0, 60), "alice")
    assert e.value.status_code == 429
    assert "zu oft" in e.value.detail


def test_the_socket_frame_ceiling_sits_above_one_turn():
    assert limits.WS_MAX_FRAME_BYTES > limits.MAX_TURN_AUDIO_BYTES
    from backend.gunicorn_worker import Worker  # pylint: disable=import-outside-toplevel

    assert Worker.CONFIG_KWARGS["ws_max_size"] == limits.WS_MAX_FRAME_BYTES


@pytest.fixture
async def anonymous_client():
    """The app with the real `require_user` and no database: every request here
    is refused before one would be needed."""
    app.dependency_overrides.pop(auth.require_user, None)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_a_declared_oversized_body_is_refused_before_the_login_check(anonymous_client):
    response = await anonymous_client.post(
        "/api/scenarios",
        content=b"{" + b" " * body_limit.MAX_BODY_BYTES + b"}",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413


async def test_an_undeclared_oversized_body_is_cut_off_as_it_arrives(anonymous_client):
    async def chunks():
        for _ in range(3):
            yield b" " * (body_limit.MAX_BODY_BYTES // 2)

    response = await anonymous_client.post(
        "/api/scenarios", content=chunks(), headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 413


async def test_a_body_under_the_ceiling_reaches_the_login_check(anonymous_client):
    response = await anonymous_client.post("/api/scenarios", json={"name": "x"})
    assert response.status_code == 401


def test_the_upload_route_has_room_for_its_documents():
    from backend.documents import MAX_TOTAL_UPLOAD_BYTES  # pylint: disable=import-outside-toplevel

    assert body_limit.limit_for(body_limit.UPLOAD_PATH) > MAX_TOTAL_UPLOAD_BYTES
    assert body_limit.limit_for("/api/scenarios") == body_limit.MAX_BODY_BYTES


async def test_an_anonymous_upload_is_refused_without_being_parsed(anonymous_client, monkeypatch):
    async def never(*_args, **_kwargs):
        raise AssertionError("the form was parsed for an anonymous caller")

    monkeypatch.setattr(Request, "form", never)
    response = await anonymous_client.post(
        body_limit.UPLOAD_PATH, files=[("files", ("x.pdf", b"%PDF-1.4", "application/pdf"))]
    )
    assert response.status_code == 401
