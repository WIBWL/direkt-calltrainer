"""The follow-up Scenario (F-60, ADR 0069, 0100); mirrors test_reverse.py on purpose."""

import json
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from openai import APIConnectionError
from sqlalchemy.orm import Session as DbSession

from shared.db.models import Feedback, FeedbackPoint, Measurement, Scenario, Session
from shared.tests.fixtures import asked, stub_completions
from backend import deletion, library, limits, retention
from backend.authored_text import FIELD_LIMITS
from backend.followups import FollowUpError, PlayedCall, draft_follow_up
from backend.tests.conftest import DRAFTED_FROM_TURNS, TEST_AUTH, a_finished_session

# pylint: disable=unused-argument,missing-function-docstring  # fixtures taken to activate them

_CARD_NAME = "Kündigungsabsicht"
_CARD_TEASER = "Kunde erwägt zu kündigen."
_IMPROVEMENTS = [
    "Bei 02:14 haben Sie „ich kümmere mich darum“ gesagt, wo nach einem Termin "
    "gefragt war.",
    "Sie haben die Rückfrage des Kunden nicht zusammengefasst.",
]
_PHASE = "Der Ton bleibt über alle drei Phasen gleich sachlich."

# The played case, carried forward by the follow-up (ADR 0069).
_DESCRIPTION = "Sie rufen bei Ihrem Anbieter an, weil Sie kündigen wollen."
_FACTS = "Vertrag seit 2019, monatlich 89 Euro, dritte Störung in sechs Wochen."
_GOAL = (
    "Eine Zusage, dass die Störung dauerhaft behoben wird. Geklärt ist die "
    "Sache mit einem Termin mit Datum. Eine Prüfzusage reicht nicht."
)
_OUTCOME = "Der Kunde legte ohne festen Termin auf."
_CALL = PlayedCall(
    scenario_name=_CARD_NAME,
    scenario_teaser=_CARD_TEASER,
    description=_DESCRIPTION,
    case_facts=_FACTS,
    call_goal=_GOAL,
    outcome=_OUTCOME,
    improvements=tuple(_IMPROVEMENTS),
    phase_language=_PHASE,
)

# The stubbed model's answer: the authoring wire's keys plus `situation`.
_SITUATION = (
    "Die Kundin aus dem letzten Gespräch ruft erneut an: Die zugesagte Gutschrift "
    "ist noch immer nicht gebucht. Geübt wird, ein verbindliches Datum zu nennen."
)
_MODEL_DRAFT = {
    "name": "Rückruf zur offenen Reklamation",
    "short_description": "Der Anrufer lässt sich diesmal nicht ohne festes Datum abwimmeln.",
    "situation": _SITUATION,
    "briefing": (
        "Sie sitzen im Support und nehmen den Rückruf entgegen. Sie dürfen ein "
        "Datum zusagen und intern eskalieren. Gut gelaufen ist das Gespräch, "
        "wenn ein Tag genannt ist."
    ),
    "description": "Sie rufen bei Ihrem Dienstleister an, weil eine Gutschrift ausbleibt.",
    "case_facts": "Gutschrift über 640 Euro, zugesagt am 3. März, bis heute nicht gebucht.",
    "call_goal": (
        "Ein Datum, an dem das Geld auf dem Konto ist. Jemand nennt einen "
        "Tag. „Wir prüfen das“ reicht nicht."
    ),
}
_REPLY = json.dumps(_MODEL_DRAFT)
# What `draft_follow_up` hands the library: `situation` under the column it is
# stored in, `description_label`, the built-in's German twin for the same panel.
_DRAFT = {
    **{k: v for k, v in _MODEL_DRAFT.items() if k != "situation"},
    "description_label": _SITUATION,
}


async def test_the_prompt_carries_the_case_and_the_improvement_points(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = stub_completions(monkeypatch, _REPLY)

    await draft_follow_up(_CALL)

    prompt = asked(calls)
    assert _CARD_NAME in prompt and _CARD_TEASER in prompt
    assert all(point in prompt for point in _IMPROVEMENTS)
    assert _PHASE in prompt


async def test_the_played_case_reaches_the_model(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = stub_completions(monkeypatch, _REPLY)

    await draft_follow_up(_CALL)

    prompt = asked(calls)
    assert all(text in prompt for text in (_DESCRIPTION, _FACTS, _GOAL))


async def test_the_wrapups_summary_says_where_the_last_call_ended(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = stub_completions(monkeypatch, _REPLY)

    await draft_follow_up(_CALL)

    assert _OUTCOME in asked(calls)


async def test_the_prompt_asks_for_the_same_matter_rather_than_a_new_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = stub_completions(monkeypatch, _REPLY)

    await draft_follow_up(_CALL)

    system = calls[0][0][0]["content"]
    assert "Carry the case forward: the same matter, a later call." in system
    assert "A call that repeats the first one" in system


async def test_the_prompt_keeps_the_case_out_of_the_description(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = stub_completions(monkeypatch, _REPLY)

    await draft_follow_up(_CALL)

    system = calls[0][0][0]["content"]
    assert "S7. description is the situation in one or two sentences" in system
    assert "read out as the opening line" in system


async def test_an_empty_case_field_is_left_out_rather_than_labelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = stub_completions(monkeypatch, _REPLY)

    await draft_follow_up(PlayedCall(_CARD_NAME, _CARD_TEASER, description=_DESCRIPTION))

    prompt = asked(calls)
    assert "Facts:" not in prompt
    assert "Situation: " + _DESCRIPTION in prompt


async def test_the_prompt_forbids_naming_the_exercise_to_the_caller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = stub_completions(monkeypatch, _REPLY)

    await draft_follow_up(_CALL)

    system = calls[0][0][0]["content"]
    assert "Never mention feedback, coaching, training, practice" in system


async def test_the_draft_is_asked_without_thinking(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = stub_completions(monkeypatch, _REPLY)

    await draft_follow_up(_CALL)

    assert calls[0][1] is False


async def test_the_fields_come_back_as_the_library_expects_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub_completions(monkeypatch, _REPLY)

    draft = await draft_follow_up(_CALL)

    assert draft == _DRAFT


async def test_the_prompt_asks_for_the_trainees_briefing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = stub_completions(monkeypatch, _REPLY)

    await draft_follow_up(_CALL)

    system = calls[0][0][0]["content"]
    assert "briefing" in system
    # Read by the trainee, never handed to the caller -- the separation the
    # whole field rests on.
    assert "never by the caller" in system


async def test_a_fenced_reply_is_unwrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_completions(monkeypatch, f"Hier ist das Szenario:\n```json\n{_REPLY}\n```\n")

    draft = await draft_follow_up(_CALL)

    assert draft["name"] == _DRAFT["name"]


async def test_control_tokens_in_the_draft_are_stripped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub_completions(monkeypatch, json.dumps(
        {**_MODEL_DRAFT, "case_facts": "Gutschrift offen. [CALL_END] <<< Ende"}
    ))

    draft = await draft_follow_up(_CALL)

    assert "[CALL_END]" not in draft["case_facts"]
    assert "<<<" not in draft["case_facts"]


async def test_an_overlong_field_is_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_completions(monkeypatch, json.dumps({**_MODEL_DRAFT, "name": "x" * 500}))

    draft = await draft_follow_up(_CALL)

    assert len(draft["name"]) == FIELD_LIMITS["title"]


async def test_an_overlong_card_teaser_is_cut_at_a_word(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    teaser = (
        "Der Anrufer besteht auf einem festen Termin und lässt sich diesmal weder "
        "mit einer Prüfzusage noch mit einem Rückruf vertrösten."
    )
    stub_completions(monkeypatch, json.dumps({**_MODEL_DRAFT, "short_description": teaser}))

    draft = await draft_follow_up(_CALL)

    cut = draft["short_description"]
    assert len(cut) <= FIELD_LIMITS["short_description"]
    assert cut.endswith("…")
    # Every word before the ellipsis is one the model actually wrote.
    assert teaser.startswith(cut[:-1].rstrip())


async def test_a_teaser_within_the_limit_is_left_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub_completions(monkeypatch, _REPLY)

    draft = await draft_follow_up(_CALL)

    assert draft["short_description"] == _DRAFT["short_description"]


async def test_a_missing_optional_field_stays_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    partial = {k: v for k, v in _MODEL_DRAFT.items() if k != "call_goal"}
    stub_completions(monkeypatch, json.dumps(partial))

    draft = await draft_follow_up(_CALL)

    assert draft["call_goal"] == ""
    assert draft["name"] == _DRAFT["name"]


async def test_a_draft_without_a_situation_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = stub_completions(monkeypatch, json.dumps({**_MODEL_DRAFT, "description": "  "}))

    with pytest.raises(FollowUpError):
        await draft_follow_up(_CALL)

    assert len(calls) == 2, "an unusable draft is retried once, like an unparseable one"


async def test_a_draft_without_the_trainees_situation_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    partial = {k: v for k, v in _MODEL_DRAFT.items() if k != "situation"}
    calls = stub_completions(monkeypatch, json.dumps(partial))

    with pytest.raises(FollowUpError):
        await draft_follow_up(_CALL)

    assert len(calls) == 2


async def test_the_prompt_has_the_caller_ring_the_trainee_in_the_situation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = stub_completions(monkeypatch, _REPLY)

    await draft_follow_up(_CALL)

    system = calls[0][0][0]["content"]
    assert "C3. situation:" in system
    assert "never the one who calls" in system
    assert '"Geübt wird"' in system


async def test_an_unparseable_reply_is_retried_once_and_then_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = stub_completions(monkeypatch, "Ich kann das leider nicht.")

    with pytest.raises(FollowUpError):
        await draft_follow_up(_CALL)

    assert len(calls) == 2


# `reference_data` per test, so the draft tests above need no database. Same
# shape as test_reverse.py on purpose.


def _store_feedback(
    db: DbSession, improvements: list[str], phase_language: str | None = _PHASE
) -> int:
    """Give the persisted Session a wrap-up, written directly: these tests are
    about what is built from it. Returns the Session's primary key."""
    session_id = db.query(Session).one().session_id
    feedback = Feedback(session_id=session_id, summary="Zusammenfassung.",
                        phase_language=phase_language, created_at=datetime.now(UTC))
    feedback.points = [
        FeedbackPoint(position=0, kind="strength", text="Klare Begrüßung."),
        *(
            FeedbackPoint(position=i, kind="improvement", text=text)
            for i, text in enumerate(improvements, start=1)
        ),
    ]
    db.add(feedback)
    db.commit()
    return session_id


def _follow_ups(db: DbSession) -> list[Scenario]:
    """Every Scenario written from a Session, read fresh -- the route used a
    session of its own."""
    db.expire_all()
    return (
        db.query(Scenario)
        .filter(Scenario.derived_from_session_id.isnot(None))
        .all()
    )


async def _ask_for_one(client: httpx.AsyncClient, extern_id) -> httpx.Response:
    return await client.post(f"/api/sessions/{extern_id}/follow-up")


async def test_the_route_stores_it_as_the_users_own_private_scenario(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    extern_id = a_finished_session()
    _store_feedback(db_session, _IMPROVEMENTS)
    stub_completions(monkeypatch, _REPLY)

    response = await _ask_for_one(api_client, extern_id)

    assert response.status_code == 200
    stored = _follow_ups(db_session)
    assert len(stored) == 1
    row = stored[0]
    assert (row.title, row.short_description) == (_DRAFT["name"], _DRAFT["short_description"])
    assert row.case_facts == _DRAFT["case_facts"]
    assert row.description_label == _SITUATION
    assert row.created_by == TEST_AUTH.sub
    assert row.visibility == "private"
    assert row.active is True
    assert row.derived_from_session_id == db_session.query(Session).one().session_id
    # Stamped with the caller's company, so sharing is a plain `visibility` flip.
    assert row.tenant_id is not None


async def test_the_answer_is_the_card_the_detail_route_serves(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    extern_id = a_finished_session()
    _store_feedback(db_session, _IMPROVEMENTS)
    stub_completions(monkeypatch, _REPLY)

    created = (await _ask_for_one(api_client, extern_id)).json()
    reloaded = (await api_client.get(f"/api/sessions/{extern_id}")).json()["follow_up"]

    assert set(created) == {"id", "name", "short_description"}
    assert created == reloaded
    assert uuid.UUID(created["id"])  # the extern_id the editor and picker use


async def test_the_info_panel_shows_the_trainees_situation_not_the_callers(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    extern_id = a_finished_session()
    _store_feedback(db_session, _IMPROVEMENTS)
    stub_completions(monkeypatch, _REPLY)

    created = (await _ask_for_one(api_client, extern_id)).json()
    shown = (await api_client.get(f"/api/scenarios/{created['id']}")).json()

    assert shown["description"] == _SITUATION


async def test_nothing_is_written_without_improvement_points(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    extern_id = a_finished_session()
    _store_feedback(db_session, [])
    calls = stub_completions(monkeypatch, _REPLY)

    response = await _ask_for_one(api_client, extern_id)

    assert response.status_code == 409
    assert not calls
    assert _follow_ups(db_session) == []


async def test_nothing_is_written_for_a_call_too_short_to_build_on(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    extern_id = a_finished_session(turns=DRAFTED_FROM_TURNS[:2])
    _store_feedback(db_session, _IMPROVEMENTS)
    calls = stub_completions(monkeypatch, _REPLY)

    response = await _ask_for_one(api_client, extern_id)

    assert response.status_code == 409
    assert not calls
    assert _follow_ups(db_session) == []


async def test_nothing_is_written_without_a_wrapup(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    extern_id = a_finished_session()
    calls = stub_completions(monkeypatch, _REPLY)

    response = await _ask_for_one(api_client, extern_id)

    assert response.status_code == 409
    assert not calls
    assert _follow_ups(db_session) == []


async def test_an_unreachable_model_is_a_503(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    extern_id = a_finished_session()
    _store_feedback(db_session, _IMPROVEMENTS)

    def fail(_messages):
        raise APIConnectionError(request=httpx.Request("POST", "http://direkt/chat"))

    stub_completions(monkeypatch, fail)

    response = await _ask_for_one(api_client, extern_id)

    assert response.status_code == 503
    assert response.json()["detail"]  # written for the user, shown as it is
    assert _follow_ups(db_session) == []
    assert db_session.query(Feedback).count() == 1


async def test_an_unusable_draft_is_a_503_too(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    extern_id = a_finished_session()
    _store_feedback(db_session, _IMPROVEMENTS)
    calls = stub_completions(monkeypatch, "Das kann ich leider nicht.")

    response = await _ask_for_one(api_client, extern_id)

    assert response.status_code == 503
    assert len(calls) == 2  # the attempt and its one retry
    assert _follow_ups(db_session) == []


async def test_a_second_press_returns_the_same_one_without_asking_the_model(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    extern_id = a_finished_session()
    _store_feedback(db_session, _IMPROVEMENTS)
    calls = stub_completions(monkeypatch, _REPLY)

    first = (await _ask_for_one(api_client, extern_id)).json()
    second = (await _ask_for_one(api_client, extern_id)).json()

    assert first == second
    assert len(calls) == 1
    assert len(_follow_ups(db_session)) == 1


async def test_past_the_hourly_budget_no_new_one_is_drafted(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    extern_id = a_finished_session()
    _store_feedback(db_session, _IMPROVEMENTS)
    calls = stub_completions(monkeypatch, _REPLY)
    monkeypatch.setattr(limits, "SCENARIO_DRAFTS", limits.RateLimit(0, 3600))

    response = await _ask_for_one(api_client, extern_id)

    assert response.status_code == 429
    assert not calls
    assert not _follow_ups(db_session)


async def test_one_already_drafted_is_returned_past_the_budget(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    extern_id = a_finished_session()
    _store_feedback(db_session, _IMPROVEMENTS)
    stub_completions(monkeypatch, _REPLY)
    first = (await _ask_for_one(api_client, extern_id)).json()
    monkeypatch.setattr(limits, "SCENARIO_DRAFTS", limits.RateLimit(0, 3600))

    again = await _ask_for_one(api_client, extern_id)

    assert again.status_code == 200
    assert again.json() == first


async def test_a_removed_follow_up_comes_back(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    extern_id = a_finished_session()
    _store_feedback(db_session, _IMPROVEMENTS)
    stub_completions(monkeypatch, _REPLY)
    created = (await _ask_for_one(api_client, extern_id)).json()
    await api_client.delete(f"/api/scenarios/{created['id']}")

    again = (await _ask_for_one(api_client, extern_id)).json()

    assert again["id"] == created["id"]
    assert _follow_ups(db_session)[0].active is True


async def test_someone_elses_session_is_a_404(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    extern_id = a_finished_session(subject="somebody-else")
    _store_feedback(db_session, _IMPROVEMENTS)
    calls = stub_completions(monkeypatch, _REPLY)

    response = await _ask_for_one(api_client, extern_id)

    assert response.status_code == 404
    assert not calls
    assert _follow_ups(db_session) == []


async def test_an_unknown_session_is_a_404(
    api_client: httpx.AsyncClient, reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = stub_completions(monkeypatch, _REPLY)

    response = await _ask_for_one(api_client, uuid.uuid4())

    assert response.status_code == 404
    assert not calls


async def test_the_measured_statistics_are_not_part_of_the_material(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    extern_id = a_finished_session()
    _store_feedback(db_session, _IMPROVEMENTS)
    measurements = db_session.query(Measurement).all()
    assert measurements, "the Session should have been measured at all"
    calls = stub_completions(monkeypatch, _REPLY)

    await _ask_for_one(api_client, extern_id)

    prompt = asked(calls)
    for measurement in measurements:
        assert measurement.metric_type.name not in prompt


async def test_the_played_scenarios_prompt_fields_reach_the_model(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    played = "Die Gutschrift wurde am 3. März zugesagt und nie gebucht."
    scenario = db_session.query(Scenario).one()
    scenario.case_facts = played
    scenario.call_goal = played
    db_session.commit()
    extern_id = a_finished_session()
    _store_feedback(db_session, _IMPROVEMENTS)
    calls = stub_completions(monkeypatch, _REPLY)

    await _ask_for_one(api_client, extern_id)

    prompt = asked(calls)
    assert played in prompt
    assert _CARD_NAME in prompt and _CARD_TEASER in prompt


async def test_the_phase_language_note_is_material_too(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    extern_id = a_finished_session()
    _store_feedback(db_session, _IMPROVEMENTS)
    calls = stub_completions(monkeypatch, _REPLY)

    await _ask_for_one(api_client, extern_id)

    assert _PHASE in asked(calls)


async def _stored_follow_up(
    client: httpx.AsyncClient, db: DbSession, monkeypatch: pytest.MonkeyPatch,
    **session_kwargs
) -> int:
    """Returns the Scenario's key: the provenance column is what these tests watch cleared."""
    extern_id = a_finished_session(**session_kwargs)
    _store_feedback(db, _IMPROVEMENTS)
    stub_completions(monkeypatch, _REPLY)
    await _ask_for_one(client, extern_id)
    return _follow_ups(db)[0].scenario_id


async def test_deleting_the_training_deactivates_its_follow_up(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario_id = await _stored_follow_up(api_client, db_session, monkeypatch)
    extern_id = db_session.query(Session).one().extern_id

    with_deleted = deletion.delete_session(db_session, TEST_AUTH.sub, extern_id)
    db_session.commit()

    assert with_deleted is True
    db_session.expire_all()
    row = db_session.get(Scenario, scenario_id)
    assert row is not None, "the Scenario must outlive the Session it came from"
    assert row.active is False
    # The FK's ON DELETE SET NULL, so the row is left pointing at nothing rather
    # than at a Session that is gone.
    assert row.derived_from_session_id is None
    assert library.get_scenario(str(row.extern_id), TEST_AUTH.sub, 1) is None


async def test_withdrawing_consent_deactivates_every_follow_up(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario_id = await _stored_follow_up(api_client, db_session, monkeypatch)

    deletion.delete_subject_sessions(db_session, TEST_AUTH.sub)
    db_session.commit()

    db_session.expire_all()
    assert db_session.get(Scenario, scenario_id).active is False


async def test_the_retention_sweep_deactivates_the_follow_up_too(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    expired = datetime.now(UTC) - retention.RETENTION - timedelta(days=1)
    scenario_id = await _stored_follow_up(
        api_client, db_session, monkeypatch, started_at=expired
    )

    assert retention.sweep(db_session) == 1
    db_session.commit()

    db_session.expire_all()
    assert db_session.get(Scenario, scenario_id).active is False


async def test_a_session_without_a_follow_up_says_so(
    api_client: httpx.AsyncClient, db_session: DbSession, reference_data
) -> None:
    extern_id = a_finished_session()
    _store_feedback(db_session, _IMPROVEMENTS)

    body = (await api_client.get(f"/api/sessions/{extern_id}")).json()

    assert body["follow_up"] is None
    # And the Persona's id, because "Starten" begins the call right there,
    # against the partner this training was played with (ADR 0050).
    assert uuid.UUID(body["persona_id"])


async def test_the_library_badges_it_as_its_own_category(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    extern_id = a_finished_session()
    _store_feedback(db_session, _IMPROVEMENTS)
    stub_completions(monkeypatch, _REPLY)
    await _ask_for_one(api_client, extern_id)

    cards = (await api_client.get("/api/scenarios")).json()

    card = next(c for c in cards if c["name"] == _DRAFT["name"])
    assert card["origin"] == "own"
    assert card["follow_up"] is True
    assert card["reverse"] is False
    assert all(c["follow_up"] is False for c in cards if c["name"] != _DRAFT["name"])
    # Categories in order: the built-in the fixture seeded comes before it.
    assert [c["follow_up"] for c in cards] == [False, True]
