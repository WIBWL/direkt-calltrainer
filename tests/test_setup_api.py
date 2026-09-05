"""Setup screen: the REST endpoints that feed persona/scenario selection.

Covers:
  F-43  setup overview  (mandatory settings visible before a session)
  F-44  persona card view  (persona picked from cards with a short profile)
  F-15/ADR 0015  persona-card selection
  F-01/F-03/F-04  the persona and scenario libraries are exposed to the client
  ADR 0001  scenario and persona are separate, independently chosen
  F-31/F-50/ADR 0009  the setup lists require a valid Keycloak token
  ADR 0041  both are served from the database-backed library
  ADR 0043  the endpoints serve display fields only; the Persona's language is
            a property of the Persona, not a Session-level choice

Uses httpx's ASGITransport rather than starlette's TestClient: the repo pins
httpx 0.28, whose Client no longer accepts the `app=` kwarg TestClient passes.
The `_override_auth` autouse fixture (conftest) makes every request here an
authenticated one unless a test drops the override.

Runs against a seeded throwaway database: since ADR 0041 the endpoints read the
persona and scenario tables rather than the modules below, so the modules are
what the seed *wrote* — which is exactly what makes comparing against them a
meaningful assertion rather than a tautology.
"""

import uuid

import httpx
import pytest

from backend import auth
from backend.app import app
# The endpoints read the seeded tables (ADR 0041), so the seed content is what
# they must return -- comparing against the test doubles would compare the
# endpoint with something it never sees.
from backend.db.seed_data import LANGUAGE_NAMES, PERSONAS as SEEDED_PERSONAS
from backend.db.seed_data import SCENARIOS as SEEDED_SCENARIOS

# pylint: disable=missing-function-docstring,redefined-outer-name


@pytest.fixture
async def client(seeded_database):  # pylint: disable=unused-argument
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health_endpoint_is_a_plain_ok(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_personas_endpoint_lists_every_persona_with_card_fields(client):
    """F-44: each persona is offered as a card with id, name, role and the
    language it speaks."""
    resp = await client.get("/api/personas")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == len(SEEDED_PERSONAS)
    # Keyed by name: `id` on the wire is the extern_id UUID now (ADR 0058), not
    # the seed slug, and the endpoint orders by name while the seed does not.
    by_name = {entry["name"]: entry for entry in body}
    for persona in SEEDED_PERSONAS:
        card = by_name[persona["name"]]
        assert uuid.UUID(card["id"])  # a valid opaque id, not the slug
        assert card["role"] == persona["role_label"]
        assert card["language"] == LANGUAGE_NAMES[persona["language_id"]]
        assert set(card) == {"id", "name", "role", "language"}  # personas aren't authored
        assert persona["name"] and persona["role_label"], "a card needs a visible name and role"


async def test_personas_endpoint_serves_the_label_not_the_prompt_role(client):
    """ADR 0043: `role_label` is what the card shows; the English prompt
    fields stay on the server."""
    body = (await client.get("/api/personas")).json()
    served = {e["role"] for e in body}
    assert served == {p["role_label"] for p in SEEDED_PERSONAS}
    for persona in SEEDED_PERSONAS:
        assert persona["role"] not in served
        assert persona["traits"] not in served
    for entry in body:
        assert "traits" not in entry and "behavior" not in entry


async def test_scenarios_endpoint_lists_every_scenario_with_its_teaser(client):
    """F-43/F-03: each scenario is offered with a human-readable teaser."""
    resp = await client.get("/api/scenarios")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == len(SEEDED_SCENARIOS)
    by_name = {entry["name"]: entry for entry in body}
    for scenario in SEEDED_SCENARIOS:
        card = by_name[scenario["name"]]
        assert uuid.UUID(card["id"])
        assert card["short_description"] == scenario["short_description"]
        assert card["herkunft"] == "vorlage"


async def test_scenarios_endpoint_withholds_the_english_call_context(client):
    """ADR 0043: `description` is prompt input, not something the setup screen
    renders — it would show the user English text in a German UI."""
    body = (await client.get("/api/scenarios")).json()
    served = {value for entry in body for value in entry.values()}
    for scenario in SEEDED_SCENARIOS:
        assert scenario["description"] not in served
    for entry in body:
        assert "description" not in entry


async def test_scenarios_endpoint_withholds_the_case(client):
    """ADR 0045: the case facts, the call goal and the success condition are
    prompt input. Serving them would hand the user the answer key to the
    exercise they are about to practise."""
    body = (await client.get("/api/scenarios")).json()
    for entry in body:
        assert set(entry) == {"id", "name", "short_description", "herkunft", "geteilt"}
        assert "case_facts" not in entry
        assert "call_goal" not in entry
        assert "success_condition" not in entry


async def test_persona_and_scenario_are_chosen_independently(client):
    """ADR 0001: any persona can run any scenario — the two lists carry no
    cross-reference or compatibility filter."""
    personas = (await client.get("/api/personas")).json()
    scenarios = (await client.get("/api/scenarios")).json()
    persona_keys = set().union(*(e.keys() for e in personas))
    scenario_keys = set().union(*(e.keys() for e in scenarios))
    assert "scenario_id" not in persona_keys and "scenario" not in persona_keys
    assert "persona_id" not in scenario_keys and "persona" not in scenario_keys


async def test_language_is_a_persona_property_not_a_separate_choice(client):
    """ADR 0043 (supersedes ADR 0022): the card says which language a Persona
    speaks, but there is nothing to pick — no language endpoint, and Scenarios
    carry no language at all."""
    routes = {getattr(r, "path", None) for r in app.routes}
    assert "/api/languages" not in routes
    for entry in (await client.get("/api/scenarios")).json():
        assert "language" not in entry and "language_id" not in entry


async def test_setup_lists_require_a_token(client):
    """F-31/F-50/ADR 0009: without a valid token the setup lists are 401,
    while /health stays open (it's an infra check)."""
    app.dependency_overrides.pop(auth.require_user, None)  # drop conftest's override
    assert (await client.get("/api/personas")).status_code == 401
    assert (await client.get("/api/scenarios")).status_code == 401
    assert (await client.get("/health")).status_code == 200
