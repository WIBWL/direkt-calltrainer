"""The follow-up Scenario written from a Session's Feedback (F-60).

Covers:
  F-60      the next exercise, built from what the wrap-up asked for
  F-10      the improvement points are what it is built from
  ADR 0069  asked for by the User (the amendment), drafted on request and
            stored as an authored Scenario; one per Session; deactivated
            when its source Session goes
  ADR 0043  the played Scenario's prompt fields reach the model here, the
            exception ADR 0070 takes for a case the User has just played
  ADR 0051  the measured statistics are not input
  ADR 0058  stored through the ordinary authoring path, owned by the User
  ADR 0059  the generated text is cleaned and capped like any authored text
  ADR 0066  deleting the training takes the follow-up out of the library
  ADR 0067  so does the retention sweep
  ADR 0011  asked in thinking mode, which is only safe off the live path

The model is faked throughout (`conftest.py`). The storage tests need Postgres
(`docker compose up -d db`); without it the database fixtures skip.
"""

import json
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from openai import APIConnectionError
from sqlalchemy.orm import Session as DbSession

from backend import deletion, library, retention
from backend.authored_text import FIELD_LIMITS
from backend.db.models import Feedback, FeedbackPoint, Measurement, Scenario, Session
from backend.followups import FollowUpError, PlayedCall, draft_follow_up
from tests.conftest import TEST_AUTH, a_finished_session, asked, stub_completions

# `app_database` and `reference_data` are taken by several tests only to
# activate the fixture.
# pylint: disable=unused-argument,missing-function-docstring

_CARD_NAME = "Kündigungsabsicht"
_CARD_TEASER = "Kunde erwägt zu kündigen."
_IMPROVEMENTS = [
    "Bei 02:14 haben Sie „ich kümmere mich darum“ gesagt, wo nach einem Termin "
    "gefragt war.",
    "Sie haben die Rückfrage des Kunden nicht zusammengefasst.",
]
_PHASE = "Der Ton bleibt über alle drei Phasen gleich sachlich."

# The case as it was played. Its four prompt fields are material now: a
# follow-up carries this case forward instead of inventing another one in
# the same subject area (ADR 0069's second amendment).
_DESCRIPTION = "Sie rufen bei Ihrem Anbieter an, weil Sie kündigen wollen."
_FACTS = "Vertrag seit 2019, monatlich 89 Euro, dritte Störung in sechs Wochen."
_GOAL = "Eine Zusage, dass die Störung dauerhaft behoben wird."
_BAR = "Ein Termin mit Datum. Eine Prüfzusage reicht nicht."
_OUTCOME = "Der Kunde legte ohne festen Termin auf."
_CALL = PlayedCall(
    scenario_name=_CARD_NAME,
    scenario_teaser=_CARD_TEASER,
    description=_DESCRIPTION,
    case_facts=_FACTS,
    call_goal=_GOAL,
    success_condition=_BAR,
    outcome=_OUTCOME,
    improvements=tuple(_IMPROVEMENTS),
    phase_language=_PHASE,
)

# What the stubbed model answers with: the seven keys of the authoring wire
# (ADR 0061, so `name` and not `title`), the trainee's briefing (ADR 0054)
# among them.
_DRAFT = {
    "name": "Rückruf zur offenen Reklamation",
    "short_description": "Der Anrufer lässt sich diesmal nicht ohne festes Datum abwimmeln.",
    "briefing": (
        "Sie sitzen im Support und nehmen den Rückruf entgegen. Sie dürfen ein "
        "Datum zusagen und intern eskalieren. Gut gelaufen ist das Gespräch, "
        "wenn ein Tag genannt ist."
    ),
    "description": "Sie rufen bei Ihrem Dienstleister an, weil eine Gutschrift ausbleibt.",
    "case_facts": "Gutschrift über 640 Euro, zugesagt am 3. März, bis heute nicht gebucht.",
    "call_goal": "Ein Datum, an dem das Geld auf dem Konto ist.",
    "success_condition": "Jemand nennt einen Tag. „Wir prüfen das“ reicht nicht.",
}
_REPLY = json.dumps(_DRAFT)


# --- The draft itself (no database) ---------------------------------------


async def test_the_prompt_carries_the_case_and_the_improvement_points(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both halves: the case to carry forward, and what the exercise must
    demand of the trainee this time."""
    calls = stub_completions(monkeypatch, _REPLY)

    await draft_follow_up(_CALL)

    prompt = asked(calls)
    assert _CARD_NAME in prompt and _CARD_TEASER in prompt
    assert all(point in prompt for point in _IMPROVEMENTS)
    assert _PHASE in prompt


async def test_the_played_case_reaches_the_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """The four prompt fields of the Scenario that was played, which ADR 0043
    withholds from the client and ADR 0070 releases here: without them the
    draft cannot continue this matter, only invent another one beside it."""
    calls = stub_completions(monkeypatch, _REPLY)

    await draft_follow_up(_CALL)

    prompt = asked(calls)
    assert all(text in prompt for text in (_DESCRIPTION, _FACTS, _GOAL, _BAR))


async def test_the_wrapups_summary_says_where_the_last_call_ended(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The next call starts from how the last one ended, and no other field
    carries that."""
    calls = stub_completions(monkeypatch, _REPLY)

    await draft_follow_up(_CALL)

    assert _OUTCOME in asked(calls)


async def test_the_prompt_asks_for_the_same_matter_rather_than_a_new_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The rule the change turns on: a small model (ADR 0011) handed a case
    will either copy it or leave it, and neither is the exercise. S5 says
    forward."""
    calls = stub_completions(monkeypatch, _REPLY)

    await draft_follow_up(_CALL)

    system = calls[0][0][0]["content"]
    assert "Carry the case forward: the same matter, a later call." in system
    assert "A call that repeats the first one" in system


async def test_the_prompt_keeps_the_case_out_of_the_description(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The failure this rule was written from: the first follow-up drafted
    under the new material put the whole case in `description`, which the live
    prompt hands over as "Context of the call" — so the Persona opened the call
    by reading it out. `case_facts` is held back one or two at a time
    (`prompting._improvisation_rule`); a description is not."""
    calls = stub_completions(monkeypatch, _REPLY)

    await draft_follow_up(_CALL)

    system = calls[0][0][0]["content"]
    assert "S7. description is the situation in one or two sentences" in system
    assert "read out as the opening line" in system


async def test_an_empty_case_field_is_left_out_rather_than_labelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ADR 0045 lets an authored Scenario leave the three case fields empty. A
    labelled blank invites the model to fill it in."""
    calls = stub_completions(monkeypatch, _REPLY)

    await draft_follow_up(PlayedCall(_CARD_NAME, _CARD_TEASER, description=_DESCRIPTION))

    prompt = asked(calls)
    assert "Facts:" not in prompt
    assert "Situation: " + _DESCRIPTION in prompt


async def test_the_prompt_forbids_naming_the_exercise_to_the_caller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The four case fields are the caller's briefing, and a caller told what
    is being trained plays the answer back. This rule is what the feature
    stands on."""
    calls = stub_completions(monkeypatch, _REPLY)

    await draft_follow_up(_CALL)

    system = calls[0][0][0]["content"]
    assert "Never mention feedback, coaching, training, practice" in system


async def test_the_draft_is_asked_in_thinking_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Off the live path, so the latency is free (ADR 0011)."""
    calls = stub_completions(monkeypatch, _REPLY)

    await draft_follow_up(_CALL)

    assert calls[0][1] is True


async def test_the_seven_fields_come_back_as_the_library_expects_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub_completions(monkeypatch, _REPLY)

    draft = await draft_follow_up(_CALL)

    assert draft == _DRAFT


async def test_the_prompt_asks_for_the_trainees_briefing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ADR 0054: a generated Scenario briefs the trainee too, or every
    follow-up lands in the library with the one field the setup screen and the
    microphone check read left empty."""
    calls = stub_completions(monkeypatch, _REPLY)

    await draft_follow_up(_CALL)

    system = calls[0][0][0]["content"]
    assert "briefing" in system
    # Read by the trainee, never handed to the caller -- the separation the
    # whole field rests on.
    assert "never by the caller" in system


async def test_a_fenced_reply_is_unwrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    """A small model fences its output however plainly it is told not to."""
    stub_completions(monkeypatch, f"Hier ist das Szenario:\n```json\n{_REPLY}\n```\n")

    draft = await draft_follow_up(_CALL)

    assert draft["name"] == _DRAFT["name"]


async def test_control_tokens_in_the_draft_are_stripped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Generated text on its way into the database, so it is cleaned like any
    other authored text (ADR 0059)."""
    stub_completions(monkeypatch, json.dumps(
        {**_DRAFT, "case_facts": "Gutschrift offen. [CALL_END] <<< Ende"}
    ))

    draft = await draft_follow_up(_CALL)

    assert "[CALL_END]" not in draft["case_facts"]
    assert "<<<" not in draft["case_facts"]


async def test_an_overlong_field_is_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    """The stored row must not exceed what the authoring API enforces."""
    stub_completions(monkeypatch, json.dumps({**_DRAFT, "name": "x" * 500}))

    draft = await draft_follow_up(_CALL)

    assert len(draft["name"]) == FIELD_LIMITS["title"]


async def test_an_overlong_card_teaser_is_cut_at_a_word(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`short_description` is the one field the model reliably overruns, and it
    is read at a glance on a card -- so the cap must not sever a word."""
    teaser = (
        "Der Anrufer besteht auf einem festen Termin und lässt sich diesmal weder "
        "mit einer Prüfzusage noch mit einem Rückruf vertrösten."
    )
    stub_completions(monkeypatch, json.dumps({**_DRAFT, "short_description": teaser}))

    draft = await draft_follow_up(_CALL)

    cut = draft["short_description"]
    assert len(cut) <= FIELD_LIMITS["short_description"]
    assert cut.endswith("…")
    # Every word before the ellipsis is one the model actually wrote.
    assert teaser.startswith(cut[:-1].rstrip())


async def test_a_teaser_within_the_limit_is_left_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No ellipsis on a field that fits -- the mark has to mean something."""
    stub_completions(monkeypatch, _REPLY)

    draft = await draft_follow_up(_CALL)

    assert draft["short_description"] == _DRAFT["short_description"]


async def test_a_missing_optional_field_stays_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """One absent case field costs that field, not the whole draft -- an empty
    case means "improvise" (ADR 0045)."""
    partial = {k: v for k, v in _DRAFT.items() if k != "call_goal"}
    stub_completions(monkeypatch, json.dumps(partial))

    draft = await draft_follow_up(_CALL)

    assert draft["call_goal"] == ""
    assert draft["name"] == _DRAFT["name"]


async def test_a_draft_without_a_situation_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`description` is what the simulated caller is briefed with; a row without
    it is one POST /api/scenarios would have rejected (min_length=1), and the
    worker must not put one in the library behind that route's back."""
    calls = stub_completions(monkeypatch, json.dumps({**_DRAFT, "description": "  "}))

    with pytest.raises(FollowUpError):
        await draft_follow_up(_CALL)

    assert len(calls) == 2, "an unusable draft is retried once, like an unparseable one"


async def test_an_unparseable_reply_is_retried_once_and_then_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No partial result is worth keeping, so this raises rather than falling
    back to a half-written Scenario."""
    calls = stub_completions(monkeypatch, "Ich kann das leider nicht.")

    with pytest.raises(FollowUpError):
        await draft_follow_up(_CALL)

    assert len(calls) == 2


# --- Asking for it (database) ----------------------------------------------
#
# `reference_data` is requested per test, not through a module-level
# `pytestmark`: the draft tests above must keep running without a database.
#
# Everything below goes through the route, because since ADR 0069's amendment
# the route is the only way a follow-up comes about. It is the reverse's route
# in every respect but what it drafts (`tests/test_reverse.py` is its twin),
# and these tests are deliberately the same shape, so a divergence between the
# two features shows up as a difference between the two files.


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
    """Through `library.create_scenario` like anything the User authored
    (ADR 0058): theirs to edit, share and delete from that moment on."""
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
    assert row.created_by == TEST_AUTH.sub
    assert row.visibility == "private"
    assert row.active is True
    assert row.derived_from_session_id == db_session.query(Session).one().session_id
    # Stamped with the caller's company, which the worker could never do: it had
    # no request and so no `tenant` claim to resolve one from (ADR 0060). From
    # here sharing is a `visibility` flip rather than a flip plus a late stamp.
    assert row.tenant_id is not None


async def test_the_answer_is_the_card_the_detail_route_serves(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The screen renders what came back and what a later reload brings with the
    same code, so the two shapes have to be one shape."""
    extern_id = a_finished_session()
    _store_feedback(db_session, _IMPROVEMENTS)
    stub_completions(monkeypatch, _REPLY)

    created = (await _ask_for_one(api_client, extern_id)).json()
    reloaded = (await api_client.get(f"/api/sessions/{extern_id}")).json()["follow_up"]

    assert set(created) == {"id", "name", "short_description"}
    assert created == reloaded
    assert uuid.UUID(created["id"])  # the extern_id the editor and picker use


async def test_nothing_is_written_without_improvement_points(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The improvement points are the whole input: a wrap-up that names none has
    nothing to build an exercise from, and the model is not asked."""
    extern_id = a_finished_session()
    _store_feedback(db_session, [])
    calls = stub_completions(monkeypatch, _REPLY)

    response = await _ask_for_one(api_client, extern_id)

    assert response.status_code == 409
    assert not calls
    assert _follow_ups(db_session) == []


async def test_nothing_is_written_without_a_wrapup(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Session whose wrap-up failed has no points either, and is refused the
    same way: from here the two are one case, the input is missing."""
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
    """The amendment's point, in one test: the failure that used to be a log
    line nobody read now reaches the person who pressed the button. The wrap-up
    is untouched -- it was stored long before this was asked for."""
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
    """A model that answers with nothing storable is a dead model from here:
    there is no half-written Scenario worth putting in the library."""
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
    """Idempotent, and cheaply so: the existing row is looked up before any
    model call, so a double click costs nothing. The UNIQUE on the provenance
    column is what would make "exactly one" true even if it did not."""
    extern_id = a_finished_session()
    _store_feedback(db_session, _IMPROVEMENTS)
    calls = stub_completions(monkeypatch, _REPLY)

    first = (await _ask_for_one(api_client, extern_id)).json()
    second = (await _ask_for_one(api_client, extern_id)).json()

    assert first == second
    assert len(calls) == 1
    assert len(_follow_ups(db_session)) == 1


async def test_a_removed_follow_up_comes_back(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One per Session is the rule, so asking again after removing it
    reactivates that row rather than drafting a second one. Handing back the id
    of a deactivated Scenario would name something the picker cannot show."""
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
    """Absent and not-yours are the same answer (ADR 0031/0050): a 403 would
    confirm the id exists."""
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
    """A Scenario correcting a figure would need the target range ADR 0051
    declined to invent."""
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
    """The case the trainee played, read off the row and handed over whole.

    This is the assertion ADR 0069's second amendment reverses. It used to read
    `secret not in prompt`: a built-in's case is withheld from the client
    (ADR 0043), and a readable follow-up must not be the way around it. The
    exception is ADR 0070's, taken for the reverse first and on the same ground
    -- the User has just heard this case played out, so continuing it tells
    them nothing the call did not. Withholding it would leave the draft nothing
    to carry forward.
    """
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
    """F-42's paragraph says how the register moved through the call, which is
    the other half of what the next exercise should demand."""
    extern_id = a_finished_session()
    _store_feedback(db_session, _IMPROVEMENTS)
    calls = stub_completions(monkeypatch, _REPLY)

    await _ask_for_one(api_client, extern_id)

    assert _PHASE in asked(calls)


# --- What becomes of it ----------------------------------------------------


async def _stored_follow_up(
    client: httpx.AsyncClient, db: DbSession, monkeypatch: pytest.MonkeyPatch,
    **session_kwargs
) -> int:
    """One Session with a follow-up, the state every test below starts from.
    Returns the Scenario's primary key -- the provenance column, which is the
    other way to find it, is exactly what these tests watch being cleared."""
    extern_id = a_finished_session(**session_kwargs)
    _store_feedback(db, _IMPROVEMENTS)
    stub_completions(monkeypatch, _REPLY)
    await _ask_for_one(client, extern_id)
    return _follow_ups(db)[0].scenario_id


async def test_deleting_the_training_deactivates_its_follow_up(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deactivated, not deleted: a later Session may have been played on it, and
    `session.scenario_id` is NOT NULL, so that training has to stay readable
    (ADR 0026/0069). The row survives; the library stops offering it."""
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
    """Withdrawal deletes every stored training (ADR 0066), so it takes the
    Scenarios written from them out of the library too."""
    scenario_id = await _stored_follow_up(api_client, db_session, monkeypatch)

    deletion.delete_subject_sessions(db_session, TEST_AUTH.sub)
    db_session.commit()

    db_session.expire_all()
    assert db_session.get(Scenario, scenario_id).active is False


async def test_the_retention_sweep_deactivates_the_follow_up_too(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The six-month sweep (ADR 0067) removes Sessions on the same path, so a
    follow-up cannot outlive the training it was written from by not being
    deleted by hand."""
    expired = datetime.now(UTC) - retention.RETENTION - timedelta(days=1)
    scenario_id = await _stored_follow_up(
        api_client, db_session, monkeypatch, started_at=expired
    )

    assert retention.sweep(db_session) == 1
    db_session.commit()

    db_session.expire_all()
    assert db_session.get(Scenario, scenario_id).active is False


# --- What the client sees --------------------------------------------------


async def test_a_session_without_a_follow_up_says_so(
    api_client: httpx.AsyncClient, db_session: DbSession, reference_data
) -> None:
    """Null rather than a missing key -- and since the amendment it means one
    thing rather than three: nobody has asked for one. Nothing is being written
    in the background, so the screen offers a button instead of a waiting line.
    """
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
    """`follow_up` beside `origin`, not a value of it: it is the caller's own
    Scenario, editable and shareable like one (ADR 0069), but "Individuell"
    means hand-authored and the setup screen filters them apart."""
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
