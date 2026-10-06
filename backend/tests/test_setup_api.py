"""The setup endpoints against a seeded database (F-43, F-44, ADR 0001, 0009, 0041, 0043)."""

# pylint: disable=duplicate-code  # each module carries its own fixture Turns on purpose


import uuid

import httpx
import pytest

# Compared with the seed, which is what the endpoints actually read.
from shared.db import models as db_models
from shared.db.seed_data import LANGUAGE_NAMES, PERSONAS as SEEDED_PERSONAS
from shared.db.seed_data import SCENARIOS as SEEDED_SCENARIOS
from shared.db.session import session_scope
from backend import auth
from backend.app import app

# pylint: disable=missing-function-docstring,redefined-outer-name

# Inactive seed Personas (no voice yet) are filtered out.
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
        assert card["language_code"] == persona["language_id"]
        # Display fields only; Personas are curated (ADR 0058).
        assert set(card) == {
            "id", "name", "role", "language", "language_code", "avatar_url",
        }
        assert persona["name"] and persona["role_label"], "a card needs a visible name and role"


async def test_personas_endpoint_serves_the_label_not_the_prompt_role(client):
    body = (await client.get("/api/personas")).json()
    served = {e["role"] for e in body}
    assert served == {p["role_label"] for p in OFFERED_PERSONAS}
    for persona in SEEDED_PERSONAS:
        assert persona["role"] not in served
        assert persona["traits"] not in served
    for entry in body:
        assert "traits" not in entry and "behavior" not in entry


async def test_persona_detail_serves_the_german_display_text(client):
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
    resp = await client.get(f"/api/personas/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_scenarios_endpoint_lists_every_scenario_with_its_teaser(client):
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
    body = (await client.get("/api/scenarios")).json()
    served = {value for entry in body for value in entry.values()}
    for scenario in SEEDED_SCENARIOS:
        assert scenario["description"] not in served
    by_name = {entry["name"]: entry for entry in body}
    for scenario in SEEDED_SCENARIOS:
        assert by_name[scenario["name"]]["description"] == scenario["description_label"]


async def test_scenarios_endpoint_withholds_the_case(client):
    body = (await client.get("/api/scenarios")).json()
    for entry in body:
        assert set(entry) == {
            "id", "name", "short_description", "briefing", "description",
            "category", "origin", "shared", "follow_up",
            # ADR 0070. Neither is prompt input: one is a casting marker,
            # the other names a Session the caller already owns.
            "reverse", "origin_session",
            # F-62: which picked goals a suggestion rests on -- the User's own.
            "recommendation",
        }
        assert "case_facts" not in entry
        assert "call_goal" not in entry


async def test_a_deactivated_scenario_is_not_offered(client):
    retired = SEEDED_SCENARIOS[0]["id"]
    with session_scope() as db:
        db.query(db_models.Scenario).filter_by(key=retired).update({"active": False})

    body = (await client.get("/api/scenarios")).json()

    assert retired not in [s["id"] for s in body], "a retired Scenario stays on offer"
    assert body, "only one Scenario was retired -- the rest must still be served"


async def test_a_deactivated_persona_is_not_offered(client):
    retired = SEEDED_PERSONAS[0]["id"]
    with session_scope() as db:
        db.query(db_models.Persona).filter_by(key=retired).update({"active": False})

    body = (await client.get("/api/personas")).json()

    assert retired not in [p["id"] for p in body], "a retired Persona stays on offer"


async def test_persona_and_scenario_are_chosen_independently(client):
    personas = (await client.get("/api/personas")).json()
    scenarios = (await client.get("/api/scenarios")).json()
    persona_keys = set().union(*(e.keys() for e in personas))
    scenario_keys = set().union(*(e.keys() for e in scenarios))
    assert "scenario_id" not in persona_keys and "scenario" not in persona_keys
    assert "persona_id" not in scenario_keys and "persona" not in scenario_keys


async def test_language_is_a_persona_property_not_a_separate_choice(client):
    routes = {getattr(r, "path", None) for r in app.routes}
    assert "/api/languages" not in routes
    for entry in (await client.get("/api/scenarios")).json():
        assert "language" not in entry and "language_id" not in entry


async def test_setup_lists_require_a_token(client):
    app.dependency_overrides.pop(auth.require_user, None)  # drop conftest's override
    assert (await client.get("/api/personas")).status_code == 401
    assert (await client.get("/api/scenarios")).status_code == 401
    assert (await client.get("/health")).status_code == 200


async def test_scenario_cards_carry_a_category_from_the_closed_vocabulary(client):
    body = (await client.get("/api/scenarios")).json()
    for entry in body:
        assert entry["category"] in db_models.SCENARIO_CATEGORIES


async def test_every_category_is_selectable(client):
    body = (await client.get("/api/scenarios")).json()
    assert {entry["category"] for entry in body} == set(db_models.SCENARIO_CATEGORIES)
