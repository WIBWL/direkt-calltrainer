"""The reverse (F-61, ADR 0070, 0100); mirrors test_followup_scenario.py on purpose."""

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from openai import APIConnectionError
from sqlalchemy.orm import Session as DbSession

from shared.db.models import Feedback, FeedbackPoint, Scenario, Session, Tenant
from shared.language_packs import get_pack
from shared.tests.fixtures import asked, stub_completions
from backend import consent, deletion, library, limits, retention
from backend.api.sessions import MIN_USER_UTTERANCES
from backend.reversals import (
    FIELD_LIMITS, GOAL_LIMIT, MAX_GOALS, ReverseError, draft_brief,
)
from backend.session.prompting import build_system_prompt
from backend.tests.conftest import DRAFTED_FROM_TURNS, TEST_PERSONAS, a_finished_session

# pylint: disable=unused-argument,missing-function-docstring  # fixtures taken to activate them

_DESCRIPTION = "The customer is calling support about an unresolved contract issue."
_FACTS = "A ticket was opened eleven days ago. A callback was promised within 48 hours."
_GOAL = (
    "Find out what is happening and get a date. The matter is settled when "
    "someone names one. A promise to look into it is not enough."
)
# A reverse must take the German display twins along.
_DESCRIPTION_DE = "Der Kunde ruft im Support an, weil ein Vertragsfall offen ist."
_FACTS_DE = "Das Ticket liegt seit elf Tagen. Ein Rückruf binnen 48 Stunden war zugesagt."
_IMPROVEMENTS = [
    "Bei 02:14 haben Sie „ich kümmere mich darum“ gesagt, wo nach einem Termin "
    "gefragt war.",
]

# What the stubbed model answers with: the four keys the briefing panel reads.
_BRIEF = {
    "situation": "Sie rufen bei Ihrem Dienstleister an, weil ein Ticket seit elf Tagen liegt.",
    "facts": "Ticket seit elf Tagen offen. Rückruf binnen 48 Stunden zugesagt.",
    "goal": (
        "Sie wollen wissen, woran es liegt, und ein Datum bekommen. Erledigt "
        "ist es, wenn Ihnen jemand einen Tag nennt."
    ),
    "goals": [
        "Nennen Sie gleich zu Beginn, worum es geht.",
        "Lassen Sie sich ein konkretes Datum nennen.",
        "Geben Sie sich nicht mit „wir prüfen das“ zufrieden.",
    ],
}
_REPLY = json.dumps(_BRIEF)


async def _draft() -> dict:
    return await draft_brief(_DESCRIPTION, _FACTS, _GOAL, _IMPROVEMENTS)


async def test_the_prompt_carries_the_played_case(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = stub_completions(monkeypatch, _REPLY)

    await _draft()

    prompt = asked(calls)
    for field in (_DESCRIPTION, _FACTS, _GOAL):
        assert field in prompt


async def test_the_prompt_carries_the_improvement_points(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = stub_completions(monkeypatch, _REPLY)

    await _draft()

    assert _IMPROVEMENTS[0] in asked(calls)


async def test_the_goals_are_asked_for_as_objectives_not_as_manner(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = stub_completions(monkeypatch, _REPLY)

    await _draft()

    prompt = asked(calls)
    assert "raise, to ask, or to" in prompt
    assert "tickable" in prompt
    assert "Never write advice about manner, tone, pace or attitude" in prompt


async def test_the_prompt_forbids_inventing_facts(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = stub_completions(monkeypatch, _REPLY)

    await _draft()

    prompt = asked(calls)
    assert "Invent nothing" in prompt
    assert "must already be in the material" in prompt


async def test_the_prompt_keeps_the_previous_call_out_of_the_briefing(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = stub_completions(monkeypatch, _REPLY)

    await _draft()

    assert "Say nothing about the previous call" in asked(calls)


async def test_the_briefing_is_asked_without_thinking(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = stub_completions(monkeypatch, _REPLY)

    await _draft()

    assert calls[0][1] is False


async def test_the_five_fields_come_back_as_the_panel_expects_them(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    stub_completions(monkeypatch, _REPLY)

    assert await _draft() == _BRIEF


async def test_a_fenced_reply_is_unwrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_completions(monkeypatch, f"```json\n{_REPLY}\n```")

    assert await _draft() == _BRIEF


async def test_control_tokens_in_the_briefing_are_stripped(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    stub_completions(monkeypatch, json.dumps({**_BRIEF, "situation": "Ruf an. [CALL_END] Jetzt."}))

    assert "[CALL_END]" not in (await _draft())["situation"]


async def test_an_overlong_field_is_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_completions(monkeypatch, json.dumps({**_BRIEF, "facts": "x" * 9000}))

    assert len((await _draft())["facts"]) == FIELD_LIMITS["facts"]


async def test_the_goal_list_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_completions(monkeypatch, json.dumps({**_BRIEF, "goals": ["Punkt."] * 12}))

    assert len((await _draft())["goals"]) == MAX_GOALS


async def test_a_long_goal_is_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_completions(monkeypatch, json.dumps({**_BRIEF, "goals": ["y" * 500]}))

    assert len((await _draft())["goals"][0]) == GOAL_LIMIT


async def test_a_long_goal_is_cut_at_a_word_and_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_completions(monkeypatch, json.dumps({**_BRIEF, "goals": ["Rechnung " * 40]}))

    goal = (await _draft())["goals"][0]
    assert len(goal) <= GOAL_LIMIT
    assert goal.endswith("…")
    assert set(goal[:-1].split()) == {"Rechnung"}, "no word cut in half"


async def test_an_empty_goal_is_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_completions(monkeypatch, json.dumps({**_BRIEF, "goals": ["Punkt.", "   ", ""]}))

    assert (await _draft())["goals"] == ["Punkt."]


async def test_a_missing_field_comes_back_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_completions(monkeypatch, json.dumps({k: v for k, v in _BRIEF.items() if k != "goal"}))

    brief = await _draft()
    assert brief["goal"] == ""
    assert brief["situation"] == _BRIEF["situation"]


async def test_an_unparseable_reply_is_retried_once_and_then_fails(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = stub_completions(monkeypatch, "Gerne! Hier ist Ihr Briefing.")

    with pytest.raises(ReverseError):
        await _draft()
    assert len(calls) == 2


def test_the_route_and_the_screen_share_one_threshold() -> None:
    screen = (
        Path(__file__).resolve().parents[2] /
        "frontend" / "src" / "components" / "FeedbackReport.tsx"
    ).read_text(encoding="utf-8")
    value = screen.split("const MIN_USER_TURNS = ", 1)[1].split(";", 1)[0]
    assert int(value) == MIN_USER_UTTERANCES


# `reference_data` per test, so the briefing tests above need no database.


def _give_the_scenario_a_case(db: DbSession) -> None:
    """The seeded reference Scenario has empty case fields; a reverse is built
    out of them, so these tests fill them in."""
    scenario = db.query(Scenario).one()
    scenario.description = _DESCRIPTION
    scenario.case_facts = _FACTS
    scenario.call_goal = _GOAL
    scenario.description_label = _DESCRIPTION_DE
    scenario.case_facts_label = _FACTS_DE
    db.commit()


def _store_feedback(db: DbSession) -> None:
    """A wrap-up on the persisted Session, written directly."""
    session_id = db.query(Session).one().session_id
    feedback = Feedback(session_id=session_id, summary="Zusammenfassung.",
                        phase_language="Sachlich durchweg.", created_at=datetime.now(UTC))
    feedback.points = [
        FeedbackPoint(position=0, kind="improvement", text=_IMPROVEMENTS[0]),
    ]
    db.add(feedback)
    db.commit()


def _reverse_row(db: DbSession) -> Scenario:
    return db.query(Scenario).filter_by(reverse=True).one()


async def test_the_route_writes_a_reverse_carrying_the_played_case(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    _give_the_scenario_a_case(db_session)
    extern_id = a_finished_session()
    _store_feedback(db_session)
    stub_completions(monkeypatch, _REPLY)

    response = await api_client.post(f"/api/sessions/{extern_id}/reverse")

    assert response.status_code == 200
    body = response.json()
    assert body["reverse_brief"] == _BRIEF

    row = _reverse_row(db_session)
    assert str(row.extern_id) == body["id"]
    # The case is copied, not re-invented -- the display twins with it, or the
    # info panel behind the card would read a built-in's case out in English.
    assert (row.description, row.case_facts, row.call_goal) == (
        _DESCRIPTION, _FACTS, _GOAL
    )
    assert (row.description_label, row.case_facts_label) == (_DESCRIPTION_DE, _FACTS_DE)
    assert row.reverse_brief == _BRIEF


async def test_the_reverse_belongs_to_the_caller_and_is_private(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    _give_the_scenario_a_case(db_session)
    extern_id = a_finished_session()
    stub_completions(monkeypatch, _REPLY)

    await api_client.post(f"/api/sessions/{extern_id}/reverse")

    row = _reverse_row(db_session)
    assert row.created_by == "test-subject"
    assert row.visibility == "private"
    assert row.tenant_id is not None


async def test_the_measured_statistics_are_not_part_of_the_material(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    _give_the_scenario_a_case(db_session)
    extern_id = a_finished_session()
    calls = stub_completions(monkeypatch, _REPLY)

    await api_client.post(f"/api/sessions/{extern_id}/reverse")

    prompt = asked(calls)
    assert "Sprechtempo" not in prompt
    assert "Wörter/min" not in prompt


async def test_a_second_press_returns_the_same_reverse_without_asking_the_model(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    _give_the_scenario_a_case(db_session)
    extern_id = a_finished_session()
    calls = stub_completions(monkeypatch, _REPLY)

    first = await api_client.post(f"/api/sessions/{extern_id}/reverse")
    second = await api_client.post(f"/api/sessions/{extern_id}/reverse")

    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert len(calls) == 1
    assert db_session.query(Scenario).filter_by(reverse=True).count() == 1


async def test_past_the_hourly_budget_no_new_one_is_drafted(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    _give_the_scenario_a_case(db_session)
    extern_id = a_finished_session()
    calls = stub_completions(monkeypatch, _REPLY)
    monkeypatch.setattr(limits, "SCENARIO_DRAFTS", limits.RateLimit(0, 3600))

    response = await api_client.post(f"/api/sessions/{extern_id}/reverse")

    assert response.status_code == 429
    assert not calls
    assert db_session.query(Scenario).filter_by(reverse=True).count() == 0


async def test_one_already_drafted_is_returned_past_the_budget(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    _give_the_scenario_a_case(db_session)
    extern_id = a_finished_session()
    stub_completions(monkeypatch, _REPLY)
    first = await api_client.post(f"/api/sessions/{extern_id}/reverse")
    monkeypatch.setattr(limits, "SCENARIO_DRAFTS", limits.RateLimit(0, 3600))

    again = await api_client.post(f"/api/sessions/{extern_id}/reverse")

    assert again.status_code == 200
    assert again.json()["id"] == first.json()["id"]


async def test_two_overlapping_requests_still_yield_one_reverse(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    _give_the_scenario_a_case(db_session)
    extern_id = a_finished_session()
    stub_completions(monkeypatch, _REPLY)
    session_pk = db_session.query(Session).one().session_id
    tenant_pk = db_session.query(Tenant).filter_by(extern_ref="default").one().tenant_id

    async def draft_and_race(*args, **kwargs):  # pylint: disable=unused-argument
        library.create_reverse(session_pk, "test-subject", tenant_pk, _BRIEF)
        return _BRIEF

    monkeypatch.setattr("backend.api.sessions.draft_brief", draft_and_race)
    response = await api_client.post(f"/api/sessions/{extern_id}/reverse")

    assert response.status_code == 200
    db_session.expire_all()
    row = _reverse_row(db_session)  # `.one()` -- a second row would fail here
    assert response.json()["id"] == str(row.extern_id)


async def test_a_removed_reverse_comes_back_selectable(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    _give_the_scenario_a_case(db_session)
    extern_id = a_finished_session()
    stub_completions(monkeypatch, _REPLY)
    first = await api_client.post(f"/api/sessions/{extern_id}/reverse")
    await api_client.delete(f"/api/scenarios/{first.json()['id']}")

    again = await api_client.post(f"/api/sessions/{extern_id}/reverse")

    assert again.json()["id"] == first.json()["id"]
    db_session.expire_all()
    assert _reverse_row(db_session).active is True


async def test_the_reverse_is_offered_in_the_library_under_its_own_flag(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    _give_the_scenario_a_case(db_session)
    extern_id = a_finished_session()
    stub_completions(monkeypatch, _REPLY)
    created = await api_client.post(f"/api/sessions/{extern_id}/reverse")

    cards = (await api_client.get("/api/scenarios")).json()

    card = next(c for c in cards if c["id"] == created.json()["id"])
    assert card["reverse"] is True
    assert card["origin"] == "own"
    assert card["origin_session"]["id"] == str(extern_id)
    assert card["origin_session"]["persona"] == "Thomas Brandt"
    # And an ordinary Scenario is not one.
    assert all(not c["reverse"] for c in cards if c["id"] != card["id"])


async def test_the_detail_route_serves_the_briefing(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    _give_the_scenario_a_case(db_session)
    extern_id = a_finished_session()
    stub_completions(monkeypatch, _REPLY)
    created = await api_client.post(f"/api/sessions/{extern_id}/reverse")

    detail = (await api_client.get(f"/api/scenarios/{created.json()['id']}")).json()

    assert detail["reverse"] is True
    assert detail["reverse_brief"] == _BRIEF
    assert detail["case_facts"] == _FACTS_DE
    assert detail["description"] == _DESCRIPTION_DE


async def test_a_reverse_read_for_a_call_swaps_the_casting(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    _give_the_scenario_a_case(db_session)
    extern_id = a_finished_session()
    stub_completions(monkeypatch, _REPLY)
    created = await api_client.post(f"/api/sessions/{extern_id}/reverse")

    # The tenant is irrelevant to this read: a reverse is private and matches
    # on `created_by`, which is the branch of `_visible_to` that applies here.
    scenario = library.get_scenario(created.json()["id"], "test-subject", tenant_id=1)

    assert scenario is not None
    assert scenario.reverse is True
    prompt = build_system_prompt(TEST_PERSONAS[0], scenario, get_pack("de"))
    assert "you are the one who answered the phone" in prompt


async def test_a_reverse_cannot_be_edited(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    _give_the_scenario_a_case(db_session)
    extern_id = a_finished_session()
    stub_completions(monkeypatch, _REPLY)
    created = await api_client.post(f"/api/sessions/{extern_id}/reverse")

    response = await api_client.patch(
        f"/api/scenarios/{created.json()['id']}",
        json={"name": "Anders", "short_description": "Anders", "description": "Anders",
              "case_facts": "", "call_goal": "", "category": ""},
    )

    assert response.status_code == 404
    db_session.expire_all()
    assert _reverse_row(db_session).case_facts == _FACTS


async def test_a_reverse_cannot_be_shared(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    _give_the_scenario_a_case(db_session)
    extern_id = a_finished_session()
    stub_completions(monkeypatch, _REPLY)
    created = await api_client.post(f"/api/sessions/{extern_id}/reverse")

    response = await api_client.put(
        f"/api/scenarios/{created.json()['id']}/visibility", json={"visibility": "tenant"}
    )

    assert response.status_code in (404, 409)
    db_session.expire_all()
    assert _reverse_row(db_session).visibility == "private"


async def test_a_client_cannot_author_a_reverse(
    api_client: httpx.AsyncClient, reference_data
) -> None:
    response = await api_client.post(
        "/api/scenarios",
        json={"name": "Fake", "short_description": "Fake", "description": "Fake",
              "case_facts": "", "call_goal": "",
              "category": "", "reverse": True},
    )

    assert response.status_code == 201
    assert response.json()["reverse"] is False


async def test_someone_elses_session_is_a_404(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    _give_the_scenario_a_case(db_session)
    extern_id = a_finished_session(subject="somebody-else")
    calls = stub_completions(monkeypatch, _REPLY)

    response = await api_client.post(f"/api/sessions/{extern_id}/reverse")

    assert response.status_code == 404
    assert not calls
    assert db_session.query(Scenario).filter_by(reverse=True).count() == 0


async def test_an_unknown_session_is_a_404(
    api_client: httpx.AsyncClient, reference_data
) -> None:
    response = await api_client.post(f"/api/sessions/{uuid.uuid4()}/reverse")

    assert response.status_code == 404


async def test_a_session_with_no_turns_is_refused(
    api_client: httpx.AsyncClient, db_session: DbSession, reference_data
) -> None:
    _give_the_scenario_a_case(db_session)
    extern_id = a_finished_session(turns=[])

    response = await api_client.post(f"/api/sessions/{extern_id}/reverse")

    assert response.status_code == 409
    assert "gesprochen" in response.json()["detail"]


async def test_a_call_too_short_for_the_screen_is_refused_too(
    api_client: httpx.AsyncClient, db_session: DbSession, reference_data
) -> None:
    _give_the_scenario_a_case(db_session)
    extern_id = a_finished_session(turns=DRAFTED_FROM_TURNS[:2])

    response = await api_client.post(f"/api/sessions/{extern_id}/reverse")

    assert response.status_code == 409
    assert db_session.query(Scenario).filter_by(reverse=True).count() == 0


async def test_a_reverse_of_a_reverse_is_refused(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    _give_the_scenario_a_case(db_session)
    a_finished_session()
    stub_completions(monkeypatch, _REPLY)
    # A Session played *on* the reverse row, which is what the User does next.
    reverse_scenario = db_session.query(Scenario).one()
    reverse_scenario.reverse = True
    db_session.commit()
    played_reverse = db_session.query(Session).one()

    response = await api_client.post(f"/api/sessions/{played_reverse.extern_id}/reverse")

    assert response.status_code == 409
    assert "Rollentausch" in response.json()["detail"]


async def test_an_unreachable_model_is_a_503(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    _give_the_scenario_a_case(db_session)
    extern_id = a_finished_session()

    def fail(_messages):
        raise APIConnectionError(request=httpx.Request("POST", "http://direkt/chat"))

    stub_completions(monkeypatch, fail)

    response = await api_client.post(f"/api/sessions/{extern_id}/reverse")

    assert response.status_code == 503
    assert "später" in response.json()["detail"]
    assert db_session.query(Scenario).filter_by(reverse=True).count() == 0


async def test_deleting_the_origin_session_leaves_the_reverse_standing(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    _give_the_scenario_a_case(db_session)
    extern_id = a_finished_session()
    stub_completions(monkeypatch, _REPLY)
    await api_client.post(f"/api/sessions/{extern_id}/reverse")

    assert (await api_client.delete(f"/api/sessions/{extern_id}")).status_code == 204

    db_session.expire_all()
    row = _reverse_row(db_session)
    assert row.origin_session_id is None
    assert row.reverse_brief == _BRIEF


async def test_the_card_says_so_when_the_origin_session_is_gone(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    _give_the_scenario_a_case(db_session)
    extern_id = a_finished_session()
    stub_completions(monkeypatch, _REPLY)
    created = await api_client.post(f"/api/sessions/{extern_id}/reverse")
    await api_client.delete(f"/api/sessions/{extern_id}")

    cards = (await api_client.get("/api/scenarios")).json()

    card = next(c for c in cards if c["id"] == created.json()["id"])
    assert card["reverse"] is True
    assert card["origin_session"] is None


async def test_withdrawing_consent_deletes_the_reverse_too(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    _give_the_scenario_a_case(db_session)
    extern_id = a_finished_session()
    stub_completions(monkeypatch, _REPLY)
    await api_client.post(f"/api/sessions/{extern_id}/reverse")

    deletion.delete_subject_sessions(db_session, "test-subject")
    db_session.commit()

    assert db_session.query(Scenario).filter_by(reverse=True).count() == 0
    # The Scenario that was played is reference data and stays.
    assert db_session.query(Scenario).count() == 1
    assert db_session.query(Session).count() == 0


async def test_withdrawing_consent_works_once_the_reverse_has_been_played(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    _give_the_scenario_a_case(db_session)
    origin = a_finished_session()
    stub_completions(monkeypatch, _REPLY)
    await api_client.post(f"/api/sessions/{origin}/reverse")
    reverse = _reverse_row(db_session)
    # Written by hand rather than through `persist`, which always picks the
    # seeded Scenario by its key -- a reverse has none.
    played_on_it = db_session.query(Session).one()
    db_session.add(Session(
        extern_id=uuid.uuid4(),
        subject_id="test-subject",
        persona_id=played_on_it.persona_id,
        scenario_id=reverse.scenario_id,
        language_code="de",
        status="completed",
        started_at=datetime.now(UTC),
        ended_at=datetime.now(UTC),
    ))
    db_session.commit()

    deletion.delete_subject_sessions(db_session, "test-subject")
    db_session.commit()

    assert db_session.query(Session).count() == 0
    assert db_session.query(Scenario).filter_by(reverse=True).count() == 0


async def test_withdrawing_consent_leaves_an_authored_scenario_alone(
    api_client: httpx.AsyncClient, db_session: DbSession, reference_data
) -> None:
    await api_client.post(
        "/api/scenarios",
        json={"name": "Eigenes", "short_description": "Eigenes", "description": "Eigenes",
              "case_facts": "", "call_goal": "", "category": ""},
    )

    deletion.delete_subject_sessions(db_session, "test-subject")
    db_session.commit()

    assert db_session.query(Scenario).filter_by(created_by="test-subject").count() == 1


async def test_the_retention_sweep_takes_the_reverse_with_it(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    _give_the_scenario_a_case(db_session)
    old = datetime.now(UTC) - retention.RETENTION - timedelta(days=1)
    extern_id = a_finished_session(started_at=old)
    stub_completions(monkeypatch, _REPLY)
    await api_client.post(f"/api/sessions/{extern_id}/reverse")

    assert retention.sweep(db_session) == 1
    db_session.commit()

    db_session.expire_all()
    assert db_session.query(Session).count() == 0
    assert db_session.query(Scenario).filter_by(reverse=True).count() == 0


def test_the_consent_module_is_untouched_by_this(reference_data) -> None:
    assert not hasattr(consent, "delete_decisions")
