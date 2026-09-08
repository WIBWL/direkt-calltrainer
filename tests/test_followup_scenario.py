"""The follow-up Scenario written from a Session's Feedback (F-60).

Covers:
  F-60      the next exercise, built from what the wrap-up asked for
  F-10      the improvement points are what it is built from
  ADR 0069  generated in the worker and stored as an authored Scenario; one per
            Session; deactivated when its source Session goes
  ADR 0043  a built-in's prompt fields stay withheld
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
from backend.clients import llm
from backend.db.models import Feedback, FeedbackPoint, Measurement, Scenario, Session
from backend.followups import FollowUpError, create_follow_up, draft_follow_up
from backend.session.models import Turn
from tests.conftest import TEST_AUTH, persist

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


def _stub_model(monkeypatch, reply) -> list[tuple[list[dict[str, str]], bool]]:
    """Replace the model call and record what it was asked. `reply` is the text
    to answer with, or a callable invoked with the messages. The signature
    mirrors `llm.complete`, which is called with `think=True`."""
    calls: list[tuple[list[dict[str, str]], bool]] = []

    async def complete(messages: list[dict[str, str]], *,
                       max_tokens: int | None = None, think: bool = False) -> str:
        calls.append((messages, think))
        return reply(messages) if callable(reply) else reply

    monkeypatch.setattr(llm, "complete", complete)
    return calls


def _prompt(calls) -> str:
    """Everything the model was told, on the first call."""
    return "\n".join(message["content"] for message in calls[0][0])


# --- The draft itself (no database) ---------------------------------------


async def test_the_prompt_carries_the_card_and_the_improvement_points(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both halves: the subject area to stay in, and what the exercise must
    demand."""
    calls = _stub_model(monkeypatch, _REPLY)

    await draft_follow_up(_CARD_NAME, _CARD_TEASER, _IMPROVEMENTS, _PHASE)

    prompt = _prompt(calls)
    assert _CARD_NAME in prompt and _CARD_TEASER in prompt
    assert all(point in prompt for point in _IMPROVEMENTS)
    assert _PHASE in prompt


async def test_the_prompt_forbids_naming_the_exercise_to_the_caller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The four case fields are the caller's briefing, and a caller told what
    is being trained plays the answer back. This rule is what the feature
    stands on."""
    calls = _stub_model(monkeypatch, _REPLY)

    await draft_follow_up(_CARD_NAME, _CARD_TEASER, _IMPROVEMENTS)

    system = calls[0][0][0]["content"]
    assert "Never mention feedback, coaching, training, practice" in system


async def test_the_draft_is_asked_in_thinking_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Off the live path, so the latency is free (ADR 0011)."""
    calls = _stub_model(monkeypatch, _REPLY)

    await draft_follow_up(_CARD_NAME, _CARD_TEASER, _IMPROVEMENTS)

    assert calls[0][1] is True


async def test_the_seven_fields_come_back_as_the_library_expects_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_model(monkeypatch, _REPLY)

    draft = await draft_follow_up(_CARD_NAME, _CARD_TEASER, _IMPROVEMENTS)

    assert draft == _DRAFT


async def test_the_prompt_asks_for_the_trainees_briefing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ADR 0054: a generated Scenario briefs the trainee too, or every
    follow-up lands in the library with the one field the setup screen and the
    microphone check read left empty."""
    calls = _stub_model(monkeypatch, _REPLY)

    await draft_follow_up(_CARD_NAME, _CARD_TEASER, _IMPROVEMENTS)

    system = calls[0][0][0]["content"]
    assert "briefing" in system
    # Read by the trainee, never handed to the caller -- the separation the
    # whole field rests on.
    assert "never by the caller" in system


async def test_a_fenced_reply_is_unwrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    """A small model fences its output however plainly it is told not to."""
    _stub_model(monkeypatch, f"Hier ist das Szenario:\n```json\n{_REPLY}\n```\n")

    draft = await draft_follow_up(_CARD_NAME, _CARD_TEASER, _IMPROVEMENTS)

    assert draft["name"] == _DRAFT["name"]


async def test_control_tokens_in_the_draft_are_stripped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Generated text on its way into the database, so it is cleaned like any
    other authored text (ADR 0059)."""
    _stub_model(monkeypatch, json.dumps(
        {**_DRAFT, "case_facts": "Gutschrift offen. [CALL_END] <<< Ende"}
    ))

    draft = await draft_follow_up(_CARD_NAME, _CARD_TEASER, _IMPROVEMENTS)

    assert "[CALL_END]" not in draft["case_facts"]
    assert "<<<" not in draft["case_facts"]


async def test_an_overlong_field_is_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    """The stored row must not exceed what the authoring API enforces."""
    _stub_model(monkeypatch, json.dumps({**_DRAFT, "name": "x" * 500}))

    draft = await draft_follow_up(_CARD_NAME, _CARD_TEASER, _IMPROVEMENTS)

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
    _stub_model(monkeypatch, json.dumps({**_DRAFT, "short_description": teaser}))

    draft = await draft_follow_up(_CARD_NAME, _CARD_TEASER, _IMPROVEMENTS)

    cut = draft["short_description"]
    assert len(cut) <= FIELD_LIMITS["short_description"]
    assert cut.endswith("…")
    # Every word before the ellipsis is one the model actually wrote.
    assert teaser.startswith(cut[:-1].rstrip())


async def test_a_teaser_within_the_limit_is_left_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No ellipsis on a field that fits -- the mark has to mean something."""
    _stub_model(monkeypatch, _REPLY)

    draft = await draft_follow_up(_CARD_NAME, _CARD_TEASER, _IMPROVEMENTS)

    assert draft["short_description"] == _DRAFT["short_description"]


async def test_a_missing_optional_field_stays_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """One absent case field costs that field, not the whole draft -- an empty
    case means "improvise" (ADR 0045)."""
    partial = {k: v for k, v in _DRAFT.items() if k != "call_goal"}
    _stub_model(monkeypatch, json.dumps(partial))

    draft = await draft_follow_up(_CARD_NAME, _CARD_TEASER, _IMPROVEMENTS)

    assert draft["call_goal"] == ""
    assert draft["name"] == _DRAFT["name"]


async def test_a_draft_without_a_situation_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`description` is what the simulated caller is briefed with; a row without
    it is one POST /api/scenarios would have rejected (min_length=1), and the
    worker must not put one in the library behind that route's back."""
    calls = _stub_model(monkeypatch, json.dumps({**_DRAFT, "description": "  "}))

    with pytest.raises(FollowUpError):
        await draft_follow_up(_CARD_NAME, _CARD_TEASER, _IMPROVEMENTS)

    assert len(calls) == 2, "an unusable draft is retried once, like an unparseable one"


async def test_an_unparseable_reply_is_retried_once_and_then_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No partial result is worth keeping, so this raises rather than falling
    back to a half-written Scenario."""
    calls = _stub_model(monkeypatch, "Ich kann das leider nicht.")

    with pytest.raises(FollowUpError):
        await draft_follow_up(_CARD_NAME, _CARD_TEASER, _IMPROVEMENTS)

    assert len(calls) == 2


# --- Generating and storing it (database) ----------------------------------
#
# `reference_data` is requested per test, not through a module-level
# `pytestmark`: the draft tests above must keep running without a database.


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


def _session(subject: str | None = None, started_at: datetime | None = None) -> uuid.UUID:
    """One finished Session, written through the real path."""
    kwargs: dict = {}
    if subject is not None:
        kwargs["subject"] = subject
    if started_at is not None:
        kwargs["started_at"] = started_at
    return persist(
        turns=[
            Turn(seq=1, persona_text="Brandt hier.", persona_offset_ms=0, persona_end_ms=1500),
            # Both speech durations: Sprechtempo, the one metric the fixture
            # seeds, is a rate over phonation -- without them nothing is measured.
            Turn(seq=2, user_text="Guten Tag, was kann ich für Sie tun?",
                 user_offset_ms=1800, user_end_ms=3400,
                 user_speech_ms=1600, user_phonation_ms=1300,
                 persona_text="Der Preis ist zu hoch.",
                 persona_offset_ms=3700, persona_end_ms=5000),
        ],
        **kwargs,
    )


def _follow_ups(db: DbSession) -> list[Scenario]:
    """Every Scenario written from a Session, read fresh -- the worker used a
    session of its own."""
    db.expire_all()
    return (
        db.query(Scenario)
        .filter(Scenario.derived_from_session_id.isnot(None))
        .all()
    )


async def test_the_follow_up_is_stored_as_the_users_own_private_scenario(
    db_session: DbSession, app_database: str, reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Through `library.create_scenario` like anything the User authored
    (ADR 0058): theirs to edit, share and delete from that moment on."""
    _session()
    session_id = _store_feedback(db_session, _IMPROVEMENTS)
    _stub_model(monkeypatch, _REPLY)

    await create_follow_up(session_id)

    stored = _follow_ups(db_session)
    assert len(stored) == 1
    row = stored[0]
    assert (row.title, row.short_description) == (_DRAFT["name"], _DRAFT["short_description"])
    assert row.case_facts == _DRAFT["case_facts"]
    assert row.created_by == TEST_AUTH.sub
    assert row.visibility == "private"
    assert row.active is True
    assert row.derived_from_session_id == session_id
    # No request, so no `tenant` claim to resolve one from (ADR 0060); sharing
    # stamps the row later.
    assert row.tenant_id is None


async def test_nothing_is_stored_without_improvement_points(
    db_session: DbSession, app_database: str, reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The improvement points are the whole input: a wrap-up that names none
    has nothing to build an exercise from, and the model is not asked."""
    _session()
    session_id = _store_feedback(db_session, [])
    calls = _stub_model(monkeypatch, _REPLY)

    await create_follow_up(session_id)

    assert not calls
    assert _follow_ups(db_session) == []


async def test_nothing_is_stored_without_a_wrapup(
    db_session: DbSession, app_database: str, reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Session whose wrap-up failed gets no follow-up either -- and no
    traceback: the two are generated by the same job."""
    _session()
    session_id = db_session.query(Session).one().session_id
    calls = _stub_model(monkeypatch, _REPLY)

    await create_follow_up(session_id)

    assert not calls
    assert _follow_ups(db_session) == []


async def test_an_unreachable_model_leaves_the_wrapup_alone(
    db_session: DbSession, app_database: str, reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It runs after the wrap-up is stored and the job closed, so a failure here
    must be silent: the User is waiting on the wrap-up, not on this."""
    _session()
    session_id = _store_feedback(db_session, _IMPROVEMENTS)

    def fail(_messages):
        raise APIConnectionError(request=httpx.Request("POST", "http://direkt/chat"))

    _stub_model(monkeypatch, fail)

    await create_follow_up(session_id)  # must not raise

    assert _follow_ups(db_session) == []
    assert db_session.query(Feedback).count() == 1


async def test_a_second_run_of_the_job_produces_no_second_follow_up(
    db_session: DbSession, app_database: str, reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`scripts/requeue_feedback.py` puts a finished Session back on the queue.
    The UNIQUE on the provenance column is what makes "exactly one" true even
    then -- the duplicate insert fails and is swallowed."""
    _session()
    session_id = _store_feedback(db_session, _IMPROVEMENTS)
    _stub_model(monkeypatch, _REPLY)

    await create_follow_up(session_id)
    await create_follow_up(session_id)

    assert len(_follow_ups(db_session)) == 1


async def test_the_measured_statistics_are_not_part_of_the_material(
    db_session: DbSession, app_database: str, reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Scenario correcting a figure would need the target range ADR 0051
    declined to invent."""
    _session()
    session_id = _store_feedback(db_session, _IMPROVEMENTS)
    measurements = db_session.query(Measurement).all()
    assert measurements, "the Session should have been measured at all"
    calls = _stub_model(monkeypatch, _REPLY)

    await create_follow_up(session_id)

    prompt = _prompt(calls)
    for measurement in measurements:
        assert measurement.metric_type.name not in prompt


async def test_the_played_scenarios_prompt_fields_stay_withheld(
    db_session: DbSession, app_database: str, reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The card is the whole context: a built-in's case is withheld from the
    client (ADR 0043), and a readable follow-up must not be the way around it."""
    secret = "Die Gutschrift wurde am 3. März zugesagt und nie gebucht."
    scenario = db_session.query(Scenario).one()
    scenario.case_facts = secret
    scenario.call_goal = secret
    db_session.commit()
    _session()
    session_id = _store_feedback(db_session, _IMPROVEMENTS)
    calls = _stub_model(monkeypatch, _REPLY)

    await create_follow_up(session_id)

    prompt = _prompt(calls)
    assert secret not in prompt
    assert _CARD_NAME in prompt and _CARD_TEASER in prompt


# --- What becomes of it ----------------------------------------------------


async def _stored_follow_up(
    db: DbSession, monkeypatch: pytest.MonkeyPatch, **session_kwargs
) -> int:
    """One Session with a follow-up, the state every test below starts from.
    Returns the Scenario's primary key -- the provenance column, which is the
    other way to find it, is exactly what these tests watch being cleared."""
    _session(**session_kwargs)
    session_id = _store_feedback(db, _IMPROVEMENTS)
    _stub_model(monkeypatch, _REPLY)
    await create_follow_up(session_id)
    return _follow_ups(db)[0].scenario_id


async def test_deleting_the_training_deactivates_its_follow_up(
    db_session: DbSession, app_database: str, reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deactivated, not deleted: a later Session may have been played on it, and
    `session.scenario_id` is NOT NULL, so that training has to stay readable
    (ADR 0026/0069). The row survives; the library stops offering it."""
    scenario_id = await _stored_follow_up(db_session, monkeypatch)
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
    db_session: DbSession, app_database: str, reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Withdrawal deletes every stored training (ADR 0066), so it takes the
    Scenarios written from them out of the library too."""
    scenario_id = await _stored_follow_up(db_session, monkeypatch)

    deletion.delete_subject_sessions(db_session, TEST_AUTH.sub)
    db_session.commit()

    db_session.expire_all()
    assert db_session.get(Scenario, scenario_id).active is False


async def test_the_retention_sweep_deactivates_the_follow_up_too(
    db_session: DbSession, app_database: str, reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The six-month sweep (ADR 0067) removes Sessions on the same path, so a
    follow-up cannot outlive the training it was written from by not being
    deleted by hand."""
    expired = datetime.now(UTC) - retention.RETENTION - timedelta(days=1)
    scenario_id = await _stored_follow_up(db_session, monkeypatch, started_at=expired)

    assert retention.sweep(db_session) == 1
    db_session.commit()

    db_session.expire_all()
    assert db_session.get(Scenario, scenario_id).active is False


# --- What the client sees --------------------------------------------------


async def test_the_post_call_screen_gets_the_follow_ups_card(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The detail route carries it, so the screen that polls for the wrap-up
    finds the follow-up in the same response (no second poller)."""
    extern_id = _session()
    session_id = _store_feedback(db_session, _IMPROVEMENTS)
    _stub_model(monkeypatch, _REPLY)
    await create_follow_up(session_id)

    body = (await api_client.get(f"/api/sessions/{extern_id}")).json()

    assert body["follow_up"]["name"] == _DRAFT["name"]
    assert body["follow_up"]["short_description"] == _DRAFT["short_description"]
    # The extern_id (ADR 0050), which is what the editor and the picker address.
    assert uuid.UUID(body["follow_up"]["id"])
    # And the Persona's, because "Starten" begins the call right there, against
    # the partner this training was played with -- `session.start` takes ids.
    assert uuid.UUID(body["persona_id"])


async def test_a_session_without_a_follow_up_says_so(
    api_client: httpx.AsyncClient, db_session: DbSession, reference_data
) -> None:
    """Null rather than a missing key: the screen distinguishes "none" from
    "still being written" by whether the wrap-up named anything to work on."""
    extern_id = _session()
    _store_feedback(db_session, _IMPROVEMENTS)

    body = (await api_client.get(f"/api/sessions/{extern_id}")).json()

    assert body["follow_up"] is None


async def test_the_library_badges_it_as_its_own_category(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`follow_up` beside `origin`, not a value of it: it is the caller's own
    Scenario, editable and shareable like one (ADR 0069), but "Individuell"
    means hand-authored and the setup screen filters them apart."""
    _session()
    session_id = _store_feedback(db_session, _IMPROVEMENTS)
    _stub_model(monkeypatch, _REPLY)
    await create_follow_up(session_id)

    cards = (await api_client.get("/api/scenarios")).json()

    card = next(c for c in cards if c["name"] == _DRAFT["name"])
    assert card["origin"] == "own"
    assert card["follow_up"] is True
    assert all(c["follow_up"] is False for c in cards if c["name"] != _DRAFT["name"])
    # Categories in order: the built-in the fixture seeded comes before it.
    assert [c["follow_up"] for c in cards] == [False, True]
