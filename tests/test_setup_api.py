"""Setup screen: the REST endpoints that feed persona/scenario selection.

Covers:
  F-43  setup overview  (mandatory settings visible before a session)
  F-44  persona card view  (persona picked from cards with a short profile)
  F-15/ADR 0015  persona-card selection
  F-01/F-03/F-04  the persona and scenario libraries are exposed to the client
  ADR 0001  scenario and persona are separate, independently chosen
  F-31/F-50/ADR 0009  the setup lists require a valid Keycloak token

Uses httpx's ASGITransport rather than starlette's TestClient: the repo pins
httpx 0.28, whose Client no longer accepts the `app=` kwarg TestClient passes.
The `_override_auth` autouse fixture (conftest) makes every request here an
authenticated one unless a test drops the override.
"""

import httpx
import pytest

from backend import auth
from backend.app import app
from backend.personas import PERSONAS
from backend.scenarios import SCENARIOS

# pylint: disable=missing-function-docstring,redefined-outer-name


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health_endpoint_is_a_plain_ok(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_personas_endpoint_lists_every_persona_with_card_fields(client):
    """F-44: each persona is offered as a card with id, name and role."""
    resp = await client.get("/api/personas")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == len(PERSONAS)
    for entry, persona in zip(body, PERSONAS):
        assert entry == {"id": persona.id, "name": persona.name, "role": persona.role}
        assert entry["name"] and entry["role"], "a card needs a visible name and role"


async def test_scenarios_endpoint_lists_every_scenario_with_a_description(client):
    """F-43/F-03: each scenario is offered with a human-readable description."""
    resp = await client.get("/api/scenarios")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == len(SCENARIOS)
    for entry, scenario in zip(body, SCENARIOS):
        assert entry == {
            "id": scenario.id,
            "name": scenario.name,
            "description": scenario.description,
        }
        assert len(entry["description"]) > 40, "the setup screen shows a real description"


async def test_persona_and_scenario_are_chosen_independently(client):
    """ADR 0001: any persona can run any scenario — the two lists carry no
    cross-reference or compatibility filter."""
    personas = (await client.get("/api/personas")).json()
    scenarios = (await client.get("/api/scenarios")).json()
    persona_keys = set().union(*(e.keys() for e in personas))
    scenario_keys = set().union(*(e.keys() for e in scenarios))
    assert "scenario_id" not in persona_keys and "scenario" not in persona_keys
    assert "persona_id" not in scenario_keys and "persona" not in scenario_keys


async def test_endpoints_expose_no_language_selector(client):
    """ADR 0006/0022: there is no global language setting; language is a
    fixed per-persona property and never surfaces as its own choice."""
    for entry in (await client.get("/api/personas")).json():
        assert "language" not in entry and "language_id" not in entry


async def test_setup_lists_require_a_token(client):
    """F-31/F-50/ADR 0009: without a valid token the setup lists are 401,
    while /health stays open (it's an infra check)."""
    app.dependency_overrides.pop(auth.require_user, None)  # drop conftest's override
    assert (await client.get("/api/personas")).status_code == 401
    assert (await client.get("/api/scenarios")).status_code == 401
    assert (await client.get("/health")).status_code == 200
