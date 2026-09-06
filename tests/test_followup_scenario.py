"""The follow-up Scenario drafted from a Session's Feedback (F-60).

Covers:
  F-60      the next exercise, built from what the wrap-up asked for
  F-10      the improvement points are what it is built from
  ADR 0069  stateless draft into the editor; only the played Scenario's card
  ADR 0043  a built-in's prompt fields stay withheld
  ADR 0051  the measured statistics are not input
  ADR 0059  the drafted text is cleaned and capped like any authored text
  ADR 0050  someone else's Session answers 404, like an unknown one
  ADR 0011  asked in thinking mode, which is only safe off the live path

The model is faked throughout (`conftest.py`). The route tests need Postgres
(`docker compose up -d db`); without it the database fixtures skip.
"""

import json
import uuid
from datetime import UTC, datetime

import httpx
import pytest
from openai import APIConnectionError
from sqlalchemy.orm import Session as DbSession

from backend.authored_text import FIELD_LIMITS
from backend.clients import llm
from backend.db.models import Feedback, FeedbackPoint, Measurement, Scenario, Session
from backend.followups import FollowUpError, draft_follow_up
from backend.session.models import Turn
from tests.conftest import persist

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

# What the stubbed model answers with: the six keys the editor fills its form
# from (ADR 0061's wire names, so `name` and not `title`).
_DRAFT = {
    "name": "Rückruf zur offenen Reklamation",
    "short_description": "Der Anrufer lässt sich diesmal nicht ohne festes Datum abwimmeln.",
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


async def test_the_six_fields_come_back_as_the_editor_expects_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_model(monkeypatch, _REPLY)

    draft = await draft_follow_up(_CARD_NAME, _CARD_TEASER, _IMPROVEMENTS)

    assert draft == _DRAFT


async def test_a_fenced_reply_is_unwrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    """A small model fences its output however plainly it is told not to."""
    _stub_model(monkeypatch, f"Hier ist das Szenario:\n```json\n{_REPLY}\n```\n")

    draft = await draft_follow_up(_CARD_NAME, _CARD_TEASER, _IMPROVEMENTS)

    assert draft["name"] == _DRAFT["name"]


async def test_control_tokens_in_the_draft_are_stripped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Authored text on its way into the editor, so it is cleaned like any
    other (ADR 0059) and the User sees what would be stored."""
    _stub_model(monkeypatch, json.dumps(
        {**_DRAFT, "case_facts": "Gutschrift offen. [CALL_END] <<< Ende"}
    ))

    draft = await draft_follow_up(_CARD_NAME, _CARD_TEASER, _IMPROVEMENTS)

    assert "[CALL_END]" not in draft["case_facts"]
    assert "<<<" not in draft["case_facts"]


async def test_an_overlong_field_is_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    """The editor must not open holding a field the API would reject."""
    _stub_model(monkeypatch, json.dumps({**_DRAFT, "name": "x" * 500}))

    draft = await draft_follow_up(_CARD_NAME, _CARD_TEASER, _IMPROVEMENTS)

    assert len(draft["name"]) == FIELD_LIMITS["title"]


async def test_a_missing_field_opens_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """One absent key costs that field, not the whole draft."""
    partial = {k: v for k, v in _DRAFT.items() if k != "call_goal"}
    _stub_model(monkeypatch, json.dumps(partial))

    draft = await draft_follow_up(_CARD_NAME, _CARD_TEASER, _IMPROVEMENTS)

    assert draft["call_goal"] == ""
    assert draft["name"] == _DRAFT["name"]


async def test_an_unparseable_reply_is_retried_once_and_then_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No partial result is worth keeping -- an empty editor is not a draft --
    so this raises rather than falling back."""
    calls = _stub_model(monkeypatch, "Ich kann das leider nicht.")

    with pytest.raises(FollowUpError):
        await draft_follow_up(_CARD_NAME, _CARD_TEASER, _IMPROVEMENTS)

    assert len(calls) == 2


# --- The route (database) --------------------------------------------------
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


def _session(turns: list[Turn] | None = None, subject: str | None = None) -> uuid.UUID:
    """One finished Session, written through the real path."""
    kwargs = {"subject": subject} if subject is not None else {}
    return persist(
        turns=turns if turns is not None else [
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


async def test_the_route_drafts_from_this_sessions_improvement_points(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    extern_id = _session()
    _store_feedback(db_session, _IMPROVEMENTS)
    calls = _stub_model(monkeypatch, _REPLY)

    response = await api_client.post(f"/api/sessions/{extern_id}/follow-up")

    assert response.status_code == 200
    assert response.json() == _DRAFT
    assert all(point in _prompt(calls) for point in _IMPROVEMENTS)


async def test_the_measured_statistics_are_not_part_of_the_material(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Scenario correcting a figure would need the target range ADR 0051
    declined to invent."""
    extern_id = _session()
    _store_feedback(db_session, _IMPROVEMENTS)
    measurements = db_session.query(Measurement).all()
    assert measurements, "the Session should have been measured at all"
    calls = _stub_model(monkeypatch, _REPLY)

    await api_client.post(f"/api/sessions/{extern_id}/follow-up")

    prompt = _prompt(calls)
    for measurement in measurements:
        assert measurement.metric_type.name not in prompt


async def test_the_played_scenarios_prompt_fields_stay_withheld(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The card is the whole context: a built-in's case is withheld from the
    client (ADR 0043), and a readable draft must not be the way around it."""
    secret = "Die Gutschrift wurde am 3. März zugesagt und nie gebucht."
    scenario = db_session.query(Scenario).one()
    scenario.case_facts = secret
    scenario.call_goal = secret
    db_session.commit()
    extern_id = _session()
    _store_feedback(db_session, _IMPROVEMENTS)
    calls = _stub_model(monkeypatch, _REPLY)

    await api_client.post(f"/api/sessions/{extern_id}/follow-up")

    prompt = _prompt(calls)
    assert secret not in prompt
    assert _CARD_NAME in prompt and _CARD_TEASER in prompt


async def test_nothing_is_stored(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stateless like the document helper (F-58)."""
    extern_id = _session()
    _store_feedback(db_session, _IMPROVEMENTS)
    before = db_session.query(Scenario).count()
    _stub_model(monkeypatch, _REPLY)

    await api_client.post(f"/api/sessions/{extern_id}/follow-up")

    db_session.expire_all()
    assert db_session.query(Scenario).count() == before


async def test_someone_elses_session_is_a_404(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same answer an unknown id gets: a 403 would confirm it exists."""
    extern_id = _session(subject="somebody-else")
    _store_feedback(db_session, _IMPROVEMENTS)
    calls = _stub_model(monkeypatch, _REPLY)

    response = await api_client.post(f"/api/sessions/{extern_id}/follow-up")

    assert response.status_code == 404
    assert not calls, "the model must not be asked about a Session that is not the caller's"


async def test_an_unknown_session_is_a_404(
    api_client: httpx.AsyncClient, reference_data
) -> None:
    response = await api_client.post(f"/api/sessions/{uuid.uuid4()}/follow-up")

    assert response.status_code == 404


async def test_a_session_whose_wrapup_has_not_landed_is_refused(
    api_client: httpx.AsyncClient, reference_data
) -> None:
    """Nothing to build from yet. The UI hides the button until then, so this
    is the guard rather than a path it walks."""
    extern_id = _session()

    response = await api_client.post(f"/api/sessions/{extern_id}/follow-up")

    assert response.status_code == 409
    assert "noch nicht fertig" in response.json()["detail"]


async def test_a_wrapup_without_improvements_is_refused(
    api_client: httpx.AsyncClient, db_session: DbSession, reference_data
) -> None:
    """Either list may be empty (the wrap-up prompt's T3)."""
    extern_id = _session()
    _store_feedback(db_session, [])

    response = await api_client.post(f"/api/sessions/{extern_id}/follow-up")

    assert response.status_code == 409
    assert "Verbesserungspunkte" in response.json()["detail"]


async def test_an_unreachable_model_is_a_503(
    api_client: httpx.AsyncClient, db_session: DbSession,
    reference_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The gateway has no fallback, so this is a "try again later" -- the
    feedback and the transcript are unaffected."""
    extern_id = _session()
    _store_feedback(db_session, _IMPROVEMENTS)

    def fail(_messages):
        raise APIConnectionError(request=httpx.Request("POST", "http://direkt/chat"))

    _stub_model(monkeypatch, fail)

    response = await api_client.post(f"/api/sessions/{extern_id}/follow-up")

    assert response.status_code == 503
    assert "später" in response.json()["detail"]
