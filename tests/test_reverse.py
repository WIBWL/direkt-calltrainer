"""The reverse of a finished Session: the same call, roles swapped (F-61).

Covers:
  F-61      the User rings and the Persona answers, from one played Session
  ADR 0070  a Scenario row with a marker, copying the case verbatim; one per
            Session; the briefing is stored and never reaches a prompt; a
            reverse is neither editable nor shareable; consent withdrawal and
            the six-month sweep take it, a single deletion does not
  ADR 0043  suspended here on purpose -- the played case reaches the client
  ADR 0051  the measured statistics are not input
  ADR 0059  the briefing is cleaned like any text written into the table
  ADR 0050  someone else's Session answers 404, like an unknown one
  ADR 0011  asked in thinking mode, which is only safe off the live path

The model is faked throughout (`conftest.py`). The route and library tests need
Postgres (`docker compose up -d db`); without it the database fixtures skip.
"""

import json
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from openai import APIConnectionError
from sqlalchemy.orm import Session as DbSession

from backend import consent, deletion, library, retention
from backend.db.models import Feedback, FeedbackPoint, Scenario, Session, Tenant
from backend.reversals import (
    FIELD_LIMITS, GOAL_LIMIT, MAX_GOALS, ReverseError, draft_brief,
)
from backend.session.language_packs import get_pack
from backend.session.prompting import build_system_prompt
from tests.conftest import TEST_PERSONAS, a_finished_session, asked, stub_completions

# `app_database` and `reference_data` are taken by several tests only to
# activate the fixture.
# pylint: disable=unused-argument,missing-function-docstring

_DESCRIPTION = "The customer is calling support about an unresolved contract issue."
_FACTS = "A ticket was opened eleven days ago. A callback was promised within 48 hours."
_GOAL = (
    "Find out what is happening and get a date. The matter is settled when "
    "someone names one. A promise to look into it is not enough."
)
# The German display twins a built-in carries beside its English prompt text
# (ADR 0043/0076). A reverse has to take them along, or the info panel behind
# its card falls back to the English.
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


# --- The briefing itself (no database) ------------------------------------


async def test_the_prompt_carries_the_played_case(monkeypatch: pytest.MonkeyPatch) -> None:
    """ADR 0070's exception to ADR 0043: the three prompt fields are exactly
    what the briefing is a translation of."""
    calls = stub_completions(monkeypatch, _REPLY)

    await _draft()

    prompt = asked(calls)
    for field in (_DESCRIPTION, _FACTS, _GOAL):
        assert field in prompt


async def test_the_prompt_carries_the_improvement_points(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """They decide which goal the checklist names first."""
    calls = stub_completions(monkeypatch, _REPLY)

    await _draft()

    assert _IMPROVEMENTS[0] in asked(calls)


async def test_the_goals_are_asked_for_as_objectives_not_as_manner(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """The checklist is the caller's agenda -- things to raise, ask and come
    away with -- and every one of them has to be tickable once the call is
    over. Advice about tone is the failure mode this rules out: it is not a
    goal, it cannot be ticked, and it is the shape a model reaches for when the
    brief says "what to pay attention to"."""
    calls = stub_completions(monkeypatch, _REPLY)

    await _draft()

    prompt = asked(calls)
    assert "raise, to ask, or to" in prompt
    assert "tickable" in prompt
    assert "Never write advice about manner, tone, pace or attitude" in prompt


async def test_the_prompt_forbids_inventing_facts(monkeypatch: pytest.MonkeyPatch) -> None:
    """The User is about to argue this case: a detail the model added is one
    the other side has never heard of."""
    calls = stub_completions(monkeypatch, _REPLY)

    await _draft()

    prompt = asked(calls)
    assert "Invent nothing" in prompt
    assert "must already be in the material" in prompt


async def test_the_prompt_keeps_the_previous_call_out_of_the_briefing(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """It is a briefing for a call that has not happened yet, not a report on
    the one behind."""
    calls = stub_completions(monkeypatch, _REPLY)

    await _draft()

    assert "Say nothing about the previous call" in asked(calls)


async def test_the_briefing_is_asked_in_thinking_mode(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """Off the live path, so the latency is free (ADR 0011)."""
    calls = stub_completions(monkeypatch, _REPLY)

    await _draft()

    assert calls[0][1] is True


async def test_the_five_fields_come_back_as_the_panel_expects_them(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    stub_completions(monkeypatch, _REPLY)

    assert await _draft() == _BRIEF


async def test_a_fenced_reply_is_unwrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    """A small model fences its output however plainly it is told not to."""
    stub_completions(monkeypatch, f"```json\n{_REPLY}\n```")

    assert await _draft() == _BRIEF


async def test_control_tokens_in_the_briefing_are_stripped(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR 0059. This text never reaches a prompt, but it is written into the
    Scenario table, and that rule does not depend on which writer filled the
    row in."""
    stub_completions(monkeypatch, json.dumps({**_BRIEF, "situation": "Ruf an. [CALL_END] Jetzt."}))

    assert "[CALL_END]" not in (await _draft())["situation"]


async def test_an_overlong_field_is_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_completions(monkeypatch, json.dumps({**_BRIEF, "facts": "x" * 9000}))

    assert len((await _draft())["facts"]) == FIELD_LIMITS["facts"]


async def test_the_goal_list_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    """A list nobody can hold in their head while talking is decoration."""
    stub_completions(monkeypatch, json.dumps({**_BRIEF, "goals": ["Punkt."] * 12}))

    assert len((await _draft())["goals"]) == MAX_GOALS


async def test_a_long_goal_is_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_completions(monkeypatch, json.dumps({**_BRIEF, "goals": ["y" * 500]}))

    assert len((await _draft())["goals"][0]) == GOAL_LIMIT


async def test_an_empty_goal_is_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_completions(monkeypatch, json.dumps({**_BRIEF, "goals": ["Punkt.", "   ", ""]}))

    assert (await _draft())["goals"] == ["Punkt."]


async def test_a_missing_field_comes_back_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing key costs that panel, not the whole briefing: the case is in
    the Scenario either way, so a thin brief still leaves a usable exercise."""
    stub_completions(monkeypatch, json.dumps({k: v for k, v in _BRIEF.items() if k != "goal"}))

    brief = await _draft()
    assert brief["goal"] == ""
    assert brief["situation"] == _BRIEF["situation"]


async def test_an_unparseable_reply_is_retried_once_and_then_fails(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """No narrative fallback, unlike the wrap-up: a Scenario carrying an
    unreadable briefing is worse than a button that says to try again."""
    calls = stub_completions(monkeypatch, "Gerne! Hier ist Ihr Briefing.")

    with pytest.raises(ReverseError):
        await _draft()
    assert len(calls) == 2


# --- The route (database) --------------------------------------------------
#
# `reference_data` is requested per test, not through a module-level
# `pytestmark`: the briefing tests above must keep running without a database.


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
    """Unlike the follow-up this one stores: a reverse is selectable again
    later, so it is a row rather than a screen (ADR 0070)."""
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
    """Like an authored Scenario in ownership (ADR 0058/0060), unlike one in
    that it can never be shared -- the briefing is built from the author's own
    wrap-up."""
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
    """ADR 0051: no target range exists, so nothing in a briefing could say
    what a figure should have been."""
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
    """`origin_session_id` is UNIQUE, and the existing row is looked up before
    any model call -- so the button is idempotent and free the second time."""
    _give_the_scenario_a_case(db_session)
    extern_id = a_finished_session()
    calls = stub_completions(monkeypatch, _REPLY)

    first = await api_client.post(f"/api/sessions/{extern_id}/reverse")
    second = await api_client.post(f"/api/sessions/{extern_id}/reverse")

    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert len(calls) == 1
    assert db_session.query(Scenario).filter_by(reverse=True).count() == 1


async def test_two_overlapping_requests_still_yield_one_reverse(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The UNIQUE constraint decides, and the loser reads the winner's row
    rather than raising: two tabs, or a double click that outran the button's
    disabled state. Simulated by writing the row behind the request's back
    between its lookup and its insert -- which is exactly the window."""
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
    """Handing back the id of a deactivated row would name something the
    selection screen cannot show."""
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
    """The card is what the "Reverse" filter runs on, and what tells the
    User which conversation it replays."""
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
    """This is how the panel gets its text during the call, and the deliberate
    exception to ADR 0043 -- for a case the User has already heard played.

    The case comes back in the display language, not in the English the prompt
    reads: `_detail` prefers the twin (ADR 0062), and a reverse of a built-in
    only has one because `_insert_reverse` copies it along with the field it
    belongs to. It did not, once, and the info panel read the case out in
    English -- which this line is here to catch.
    """
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
    """The seam between the row and the prompt, and the only place the two
    halves of ADR 0070 meet: `library.get_scenario` is what the WebSocket
    handshake calls, and the marker it carries is what `build_system_prompt`
    branches on. Everything else about the casting is pinned in
    `test_reverse_prompt.py`, against the value object."""
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
    """It copies a case that was played; editing it would leave a row claiming
    to replay a conversation it no longer matches (ADR 0070). 404, the same
    answer a row that is not the caller's gets."""
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
    """Sharing it would hand colleagues a reading of the author's own
    feedback."""
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
    """`reverse` is not an authorable field: the only writer is the route
    above, which is what keeps `origin_session_id` and the briefing consistent
    with the marker."""
    response = await api_client.post(
        "/api/scenarios",
        json={"name": "Fake", "short_description": "Fake", "description": "Fake",
              "case_facts": "", "call_goal": "",
              "category": "", "reverse": True},
    )

    assert response.status_code == 201
    assert response.json()["reverse"] is False


# --- Refusals --------------------------------------------------------------


async def test_someone_elses_session_is_a_404(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same answer an unknown id gets: a 403 would confirm it exists."""
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
    """Nothing was said, so there is no call to stand on the other side of."""
    _give_the_scenario_a_case(db_session)
    extern_id = a_finished_session(turns=[])

    response = await api_client.post(f"/api/sessions/{extern_id}/reverse")

    assert response.status_code == 409
    assert "gesprochen" in response.json()["detail"]


async def test_a_reverse_of_a_reverse_is_refused(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The roles are already swapped; swapping them again is the original call
    with a copied briefing."""
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
    """The gateway has no fallback, so this is a "try again later" -- and
    nothing is written, so the next attempt starts clean."""
    _give_the_scenario_a_case(db_session)
    extern_id = a_finished_session()

    def fail(_messages):
        raise APIConnectionError(request=httpx.Request("POST", "http://direkt/chat"))

    stub_completions(monkeypatch, fail)

    response = await api_client.post(f"/api/sessions/{extern_id}/reverse")

    assert response.status_code == 503
    assert "später" in response.json()["detail"]
    assert db_session.query(Scenario).filter_by(reverse=True).count() == 0


# --- Deletion (ADR 0066/0067 addendum in ADR 0070) -------------------------


async def test_deleting_the_origin_session_leaves_the_reverse_standing(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`ON DELETE SET NULL`: the reverse outlives the conversation it replays,
    because a Session played on it points at the row (ADR 0052)."""
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
    """ADR 0070's addendum to ADR 0066: the briefing is written from that
    person's own wrap-up, so leaving the row would leave a reading of feedback
    whose conversation has just been deleted."""
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
    """The case the deletion order exists for: a Session played *on* the
    reverse points at that row through `session.scenario_id`, which carries no
    `ondelete` at all (ADR 0052). Removing the row before its Sessions would be
    refused by the database."""
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
    """It is the User's own work about a case, not a record of a call they
    had -- the distinction the deletion rule turns on."""
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
    """The other half of ADR 0070's deletion rule, and the half nothing else
    would notice: the six-month sweep (ADR 0067) removes the reverse along with
    the Session it replays.

    This test asserted the opposite until ADR 0070 was amended. The reason it
    changed: the briefing is written from that call's own wrap-up, and once the
    call has expired what survives is a text about how a person argued with its
    source destroyed. The line now runs between the paths where somebody is
    deciding about that row -- a single deletion, where the User is present,
    is told the reverse stays and can remove it herself -- and the two that run
    with nobody there, the withdrawal and this sweep.
    """
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
    """A guard on the boundary rather than on behaviour: the reverse deletion
    rides on the withdrawal path, and must never reach the consent log itself
    (ADR 0068)."""
    assert not hasattr(consent, "delete_decisions")
