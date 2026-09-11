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
from backend.db import models as db_models
from backend.db.seed_data import LANGUAGE_NAMES, PERSONAS as SEEDED_PERSONAS
from backend.db.seed_data import SCENARIOS as SEEDED_SCENARIOS
from backend.db.session import session_scope

# pylint: disable=missing-function-docstring,redefined-outer-name

# The Personas actually on offer. A seed entry may carry `active: False` while
# something it needs to run is still missing (a KugelAudio voice, today), and
# `library.list_personas` filters those out -- so the endpoint serves a subset
# of the seed, and these tests compare against that subset.
OFFERED_PERSONAS = [p for p in SEEDED_PERSONAS if p.get("active", True)]


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
    assert len(body) == len(OFFERED_PERSONAS)
    # Keyed by name: `id` on the wire is the extern_id UUID now (ADR 0058), not
    # the seed slug, and the endpoint orders by name while the seed does not.
    by_name = {entry["name"]: entry for entry in body}
    for persona in OFFERED_PERSONAS:
        card = by_name[persona["name"]]
        assert uuid.UUID(card["id"])  # a valid opaque id, not the slug
        assert card["role"] == persona["role_label"]
        assert card["language"] == LANGUAGE_NAMES[persona["language_id"]]
        # `avatar_url` is the portrait's path; no authoring fields, since
        # Personas are curated (ADR 0058).
        assert set(card) == {"id", "name", "role", "language", "avatar_url"}
        assert persona["name"] and persona["role_label"], "a card needs a visible name and role"


async def test_personas_endpoint_serves_the_label_not_the_prompt_role(client):
    """ADR 0043: `role_label` is what the card shows; the English prompt
    fields stay on the server."""
    body = (await client.get("/api/personas")).json()
    served = {e["role"] for e in body}
    assert served == {p["role_label"] for p in OFFERED_PERSONAS}
    for persona in SEEDED_PERSONAS:
        assert persona["role"] not in served
        assert persona["traits"] not in served
    for entry in body:
        assert "traits" not in entry and "behavior" not in entry


async def test_persona_detail_serves_the_german_display_text(client):
    """F-44 / ADR 0043: the info panel behind a card is fed by
    `GET /api/personas/{id}`, and every text on it is the UI-language
    display field -- never the English prompt field beside it."""
    cards = (await client.get("/api/personas")).json()
    card = next(c for c in cards if c["name"] == "Marcel Kropp")

    resp = await client.get(f"/api/personas/{card['id']}")
    assert resp.status_code == 200
    detail = resp.json()

    seeded = next(p for p in SEEDED_PERSONAS if p["name"] == "Marcel Kropp")
    assert detail["role"] == seeded["role_label"]
    assert detail["traits"] == seeded["traits_label"]
    assert detail["training_goal"] == seeded["training_goal"]
    assert detail["objections"] == seeded["objection_labels"]
    assert set(detail) == {
        "id", "name", "role", "language", "avatar_url", "traits", "training_goal",
        "objections",
    }


async def test_persona_detail_withholds_the_english_prompt_fields(client):
    """ADR 0043, the same rule the card route follows: `role`, `traits`,
    `behavior` and an objection's English `text` brief the model and stay on
    the server. The panel would be the obvious place to leak them, because
    it shows a field of each name."""
    cards = (await client.get("/api/personas")).json()
    served = []
    for card in cards:
        detail = (await client.get(f"/api/personas/{card['id']}")).json()
        served.append(detail["traits"])
        served.extend(detail["objections"])
        assert "behavior" not in detail

    for persona in SEEDED_PERSONAS:
        assert persona["traits"] not in served
        assert persona["behavior"] not in served
        for objection in persona["objections"]:
            assert objection not in served


async def test_persona_detail_404s_for_an_unknown_id(client):
    """An id that is not a Persona's answers 404, exactly as an inactive
    one does -- an inactive Persona is not on offer either."""
    resp = await client.get(f"/api/personas/{uuid.uuid4()}")
    assert resp.status_code == 404


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
        assert card["origin"] == "builtin"
        assert card["category"] == scenario["category"]
        # ADR 0054: the trainee's own briefing rides on the card, because the
        # setup screen and the microphone check both read it from this list.
        assert card["briefing"] == scenario["briefing"]


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
        assert set(entry) == {
            "id", "name", "short_description", "briefing", "category", "origin",
            "shared", "follow_up",
            # ADR 0070. Neither is prompt input: one is a casting marker,
            # the other names a Session the caller already owns.
            "reverse", "origin_session",
        }
        assert "case_facts" not in entry
        assert "call_goal" not in entry
        assert "success_condition" not in entry


async def test_a_deactivated_scenario_is_not_offered(client):
    """A Scenario dropped from the seed is deactivated, never deleted -- stored
    Sessions reference it (ADR 0026). `active` is therefore the whole mechanism
    that takes it out of the selection, and the endpoint has to honour it, the
    way the persona list already did.
    """
    retired = SEEDED_SCENARIOS[0]["id"]
    with session_scope() as db:
        db.query(db_models.Scenario).filter_by(key=retired).update({"active": False})

    body = (await client.get("/api/scenarios")).json()

    assert retired not in [s["id"] for s in body], "a retired Scenario stays on offer"
    assert body, "only one Scenario was retired -- the rest must still be served"


async def test_a_deactivated_persona_is_not_offered(client):
    """The same rule on the persona side, which had no test of its own either."""
    retired = SEEDED_PERSONAS[0]["id"]
    with session_scope() as db:
        db.query(db_models.Persona).filter_by(key=retired).update({"active": False})

    body = (await client.get("/api/personas")).json()

    assert retired not in [p["id"] for p in body], "a retired Persona stays on offer"


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


async def test_scenario_cards_carry_a_category_from_the_closed_vocabulary(client):
    """ADR 0072: the card carries the F-03 call context the library's category
    filter runs on, and it is a value from the vocabulary the CHECK constraint
    enforces, not the free text it replaces."""
    body = (await client.get("/api/scenarios")).json()
    for entry in body:
        assert entry["category"] in db_models.SCENARIO_CATEGORIES


async def test_every_category_is_selectable(client):
    """F-03: the library covers every call context, so none of the filter's
    options is empty on a fresh install."""
    body = (await client.get("/api/scenarios")).json()
    assert {entry["category"] for entry in body} == set(db_models.SCENARIO_CATEGORIES)
