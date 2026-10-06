"""The wrap-up prompt as handed to the model (F-09, F-10, F-37, F-42, ADR 0004, 0049, 0051)."""

from types import SimpleNamespace

import pytest

from shared.clients.llm import _strip_reasoning
from shared.db import models as db_models
from shared.db.seed_data import FOCUS_GOALS
from shared.feedback import metrics
from shared.language_packs import LANGUAGE_PACKS
from worker.generator import (
    _ask,
    _dossier,
    _goal_without_criterion,
    _in_language,
    _LANGUAGE_NAMES_EN,
    _messages,
    _NO_WRAPUP,
    _NOTHING_SAID,
    _occasion,
    _SETTLEMENT_MARKER,
    _unfenced_text,
    _without_turn_markers,
    _Wrapup,
)

# The prompt builder and the response model are the units under test.
# pylint: disable=redefined-outer-name


@pytest.fixture
def system_prompt() -> str:
    """The system half of the wrap-up prompt, for an otherwise empty call."""
    return _messages("Transcript, timestamped from the start of the call:", "German")[0][
        "content"
    ]


def test_prompt_names_the_three_phases(system_prompt: str) -> None:
    assert "Opening:" in system_prompt
    assert "Core business:" in system_prompt
    assert "Closing:" in system_prompt


def test_prompt_states_the_register_each_phase_calls_for(system_prompt: str) -> None:
    assert "warm, then factual, then warm again" in system_prompt
    assert "stays in a single register" in system_prompt


def test_prompt_gives_the_closing_the_most_room(system_prompt: str) -> None:
    assert "Give the closing more of your text than the other two phases" in system_prompt


def test_phase_block_stays_off_the_score_ladder(system_prompt: str) -> None:
    assert "never grade the call (N1)" in system_prompt
    assert "N1. No score, grade, rating, percentage, or star" in system_prompt


def test_prompt_asks_for_six_keys_including_the_phase_and_tone_blocks(
    system_prompt: str,
) -> None:
    assert (
        "summary, phase_language, tone_fit, pressure_turns, strengths, improvements"
        in system_prompt
    )
    assert '"phase_language": "one paragraph' in system_prompt
    assert '"tone_fit": "one paragraph' in system_prompt
    assert '"pressure_turns": [<ids of the Caller utterances' in system_prompt
    assert "The six keys stay in English" in system_prompt
    assert "five keys" not in system_prompt
    assert "four keys" not in system_prompt
    assert "three keys" not in system_prompt


def test_the_prose_blocks_carry_no_figures(system_prompt: str) -> None:
    assert "F5. The summary and the phase_language block carry no figures" in system_prompt
    assert "never one in brackets after a statement" in system_prompt
    assert "H8. No figures in this block either" in system_prompt
    # And the silent check at the end asks for it again, which is the one the
    # model actually runs over its own answer.
    assert "neither the summary nor phase_language" in system_prompt


def test_the_tone_block_starts_from_the_occasion_and_not_from_the_figures(
    system_prompt: str,
) -> None:
    assert "# The tone_fit block" in system_prompt
    assert "G1. Start from the occasion, not from the figures." in system_prompt
    assert "the quotation is what carries the observation" in system_prompt


def test_the_tone_block_rules_out_a_correct_register_for_a_kind_of_call(
    system_prompt: str,
) -> None:
    assert "There is no correct register for a kind of call" in system_prompt
    assert "Do not manufacture a mismatch" in system_prompt


def test_the_tone_block_is_kept_apart_from_the_phase_block(system_prompt: str) -> None:
    assert "Do not repeat the phase_language block" in system_prompt


def test_the_dossier_names_the_occasion_before_the_statistics() -> None:
    dossier, _ = _dossier(_session_with())

    assert "The occasion of this call" in dossier
    assert "line that has been down since Monday" in dossier
    assert "Get a repair date" in dossier, "what the caller wanted is the occasion"
    assert dossier.index("The occasion") < dossier.index("Measured statistics")


def test_the_prompt_lists_every_focus_goal_key_it_may_assign(system_prompt: str) -> None:
    for goal in FOCUS_GOALS:
        assert f"    {goal['id']}: {goal['title']}" in system_prompt

    assert '"goal": "<one key from the list, or an empty string>"' in system_prompt


def test_an_empty_goal_is_offered_as_a_normal_answer(system_prompt: str) -> None:
    assert "A4. Write an empty string when nothing on the list fits" in system_prompt
    assert "Never force a fit" in system_prompt


def test_the_goal_may_not_change_what_a_point_says(system_prompt: str) -> None:
    assert "A5. The goal never changes what the point says" in system_prompt
    assert "delete the key instead" in system_prompt


def test_the_habit_goals_are_ruled_out_in_the_prompt(system_prompt: str) -> None:
    assert "Never assign either." in system_prompt


def test_the_dossier_withholds_the_success_condition() -> None:
    dossier, _ = _dossier(_session_with())

    assert "The matter is settled when" not in dossier
    assert "named engineer" not in dossier
    # The criterion is cut off the goal, not the goal dropped.
    assert "Get a repair date" in dossier


def test_prompt_forbids_markup_inside_the_phase_paragraph(system_prompt: str) -> None:
    assert "no headings, no bullet characters, no line breaks" in system_prompt


def test_answer_carrying_the_phase_paragraph_parses() -> None:
    wrapup = _Wrapup.model_validate_json(
        '{"summary": "Kurz.", '
        '"phase_language": "Im Einstieg klangen Sie warm.", '
        '"strengths": [], "improvements": []}'
    )

    assert wrapup.phase_language == "Im Einstieg klangen Sie warm."


def test_answer_dropping_the_phase_paragraph_still_parses() -> None:
    wrapup = _Wrapup.model_validate_json(
        '{"summary": "Kurz.", "strengths": [], "improvements": []}'
    )

    assert wrapup.phase_language == ""


def test_narrative_fallback_carries_no_phase_text() -> None:
    assert _Wrapup(summary="Freitext ohne JSON.").phase_language == ""


def test_every_supported_language_has_a_name_for_the_prompt() -> None:
    assert set(LANGUAGE_PACKS) <= set(_LANGUAGE_NAMES_EN)


def test_the_language_name_is_what_the_model_is_told_to_write_in() -> None:
    system = _messages("dossier", _LANGUAGE_NAMES_EN["en"])[0]["content"]

    assert "Every value you write is in English" in system


async def test_the_wrapup_is_asked_without_thinking(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []
    # Tells "left at llm.complete's default" apart from "explicitly None",
    # which is what the PDF summary passes and this call must not.
    unset = object()

    async def fake_complete(messages, *, max_tokens=unset, think=False):
        calls.append({"messages": messages, "max_tokens": max_tokens, "think": think})
        return '{"summary": "Kurz.", "phase_language": "", "strengths": [], "improvements": []}'

    monkeypatch.setattr("shared.clients.llm.complete", fake_complete)

    await _ask("Transcript, timestamped from the start of the call:", "German")

    assert len(calls) == 1, "one attempt is enough when the answer validates"
    assert calls[0]["think"] is False
    # The wrap-up keeps the cap; only the PDF summary (F-58) drops it, having a
    # character cap instead. Uncapped, a repetition loop could run to the job timeout.
    assert calls[0]["max_tokens"] is unset
    assert "Transcript" in calls[0]["messages"][1]["content"]


def test_an_unfinished_reasoning_trace_yields_no_answer() -> None:
    assert _strip_reasoning("<think>Let me consider {\"summary\": ...") == ""
    assert _strip_reasoning("<think>done</think>\n{\"summary\": \"Kurz.\"}") == '{"summary": "Kurz."}'


def _measurement(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    key: str, name: str, unit: str | None, value: float, detail=None,
    segment: str = db_models.SEGMENT_CALL,
):
    return SimpleNamespace(
        value=value,
        detail_json=detail,
        segment=segment,
        metric_type=SimpleNamespace(key=key, name=name, unit=unit),
    )


def _session_with(*measurements) -> SimpleNamespace:
    # `call_goal` is set although unread: it holds the criterion the test keeps out.
    return SimpleNamespace(
        measurements=list(measurements),
        turns=[],
        scenario=SimpleNamespace(
            reverse=False,
            description="A customer rings about a line that has been down since Monday.",
            # Carries the settlement criterion, as every seeded goal does since
            # migration 3ce81b27af40 merged `success_condition` into it.
            call_goal=(
                "Get a repair date and some acknowledgement of the trouble. The "
                "matter is settled when a named engineer and a date the customer "
                "accepts have been given."
            ),
        ),
    )


def test_the_dossier_describes_loudness_instead_of_quoting_its_span() -> None:
    curve = [65.0 + (index % 5) - 2 for index in range(600)]
    for index in range(450, 510):
        curve[index] += 10.0

    dossier, _ = _dossier(_session_with(
        _measurement("loudness", "Lautstärke", "dB", 12.3, {"curve_db": curve}),
    ))

    assert "Lautstärke: 12.3 dB" not in dossier
    assert "Loudness course:" in dossier
    assert "louder stretch" in dossier


def test_the_other_statistics_still_reach_the_model_as_figures() -> None:
    dossier, _ = _dossier(_session_with(
        _measurement("pace", "Sprechtempo", "WPM", 132.0),
        _measurement("questions", "Fragen", "Anzahl", 4.0),
    ))

    assert "Sprechtempo: 132.0 WPM" in dossier
    assert "Fragen: 4.0 Anzahl" in dossier


def test_a_loudness_measurement_without_a_curve_adds_no_line() -> None:
    dossier, _ = _dossier(_session_with(
        _measurement("loudness", "Lautstärke", "dB", 12.3, None),
    ))

    assert "Loudness course" not in dossier
    assert "Lautstärke" not in dossier


def test_the_prompt_forbids_the_turn_id_in_a_text_value(system_prompt: str) -> None:
    assert "N5." in system_prompt
    assert "Never write a turn id inside a text value" in system_prompt


@pytest.mark.parametrize("written, expected", [
    ('Bei [turn_id=12] 02:14 sagten Sie: „Ich schaue mal.“',
     'Bei 02:14 sagten Sie: „Ich schaue mal.“'),
    ('turn_id=12 Sie blieben sachlich.', 'Sie blieben sachlich.'),
    ('Sie sagten (turn_id 7), dass Sie sich melden.',
     'Sie sagten, dass Sie sich melden.'),
    ('[Turn 12] Ihr Einstieg war warm.', 'Ihr Einstieg war warm.'),
    ('Sie liessen ihn ausreden [turn-id: 4]; das half.',
     'Sie liessen ihn ausreden; das half.'),
])
def test_a_copied_turn_marker_never_reaches_the_stored_text(
    written: str, expected: str,
) -> None:
    assert _without_turn_markers(written) == expected


def test_a_sentence_that_merely_reads_like_a_marker_is_left_alone() -> None:
    prose = "In Turn 12 haben Sie zugehört."
    assert _without_turn_markers(prose) == prose
    assert _without_turn_markers("Bei 02:14 sagten Sie: „Moment.“") == (
        "Bei 02:14 sagten Sie: „Moment.“"
    )


def test_the_sentences_written_here_follow_the_sessions_language() -> None:
    assert _in_language(_NOTHING_SAID, "German").startswith("In diesem Training")
    assert "nothing to review" in _in_language(_NOTHING_SAID, "English")
    assert _in_language(_NO_WRAPUP, "German").startswith("Für dieses Gespräch")
    assert _in_language(_NO_WRAPUP, "English").startswith("No feedback")


def test_a_language_without_a_sentence_gets_the_german_one() -> None:
    assert _in_language(_NOTHING_SAID, "Finnish") == _in_language(_NOTHING_SAID, "German")


def test_only_the_whole_calls_statistics_reach_the_dossier() -> None:
    session = _session_with(
        _measurement("pace", "Sprechtempo", "Wörter/min", 145.0),
        _measurement("pace", "Sprechtempo", "Wörter/min", 172.0,
                     segment=db_models.SEGMENT_PRESSURE),
        _measurement("pace", "Sprechtempo", "Wörter/min", 131.0,
                     segment=db_models.SEGMENT_REST),
    )

    dossier, _ = _dossier(session)

    assert dossier.count("Sprechtempo") == 1
    assert "145.0" in dossier and "172.0" not in dossier and "131.0" not in dossier


def test_the_loudness_course_is_the_whole_calls_curve() -> None:
    session = _session_with(
        _measurement("loudness", "Lautstärke", "dB", 9.0,
                     detail={"curve_db": [40.0] * 30}, segment=db_models.SEGMENT_PRESSURE),
        _measurement("loudness", "Lautstärke", "dB", 12.0,
                     detail={"curve_db": [70.0] * 30}),
    )

    dossier, _ = _dossier(session)

    assert metrics.describe_loudness_course([70.0] * 30) in dossier


def test_a_reply_that_never_validated_is_not_shown_as_the_summary() -> None:
    cut_off = '{"summary": "Sie haben klar nachgefragt.", "phase_language": "Sach'

    assert _unfenced_text(cut_off, "German") == _NO_WRAPUP["German"]
    assert _unfenced_text('["Klare Nachfrage."]', "German") == _NO_WRAPUP["German"]


def test_real_prose_still_becomes_the_fallback_summary() -> None:
    prose = "Sie haben ruhig und klar nachgefragt, und das Gespräch blieb sachlich."

    assert _unfenced_text(prose, "German") == prose


def test_every_seeded_goal_marks_where_its_criterion_starts() -> None:
    from shared.db.seed_data import SCENARIOS  # pylint: disable=import-outside-toplevel

    missing = [s["id"] for s in SCENARIOS if _SETTLEMENT_MARKER not in s["call_goal"]]

    assert not missing, f"call_goal without the settlement sentence: {missing}"


def test_an_authored_goal_with_no_criterion_goes_in_whole() -> None:
    own = SimpleNamespace(call_goal="Klären, ob die Lieferung diese Woche noch kommt.")

    assert _goal_without_criterion(own) == "Klären, ob die Lieferung diese Woche noch kommt."


def test_a_goal_that_is_only_a_criterion_adds_no_line() -> None:
    odd = SimpleNamespace(
        description="Eine Situation.",
        call_goal=f"{_SETTLEMENT_MARKER} the date is confirmed.",
        reverse=False,
    )

    assert _goal_without_criterion(odd) == ""
    assert "What the caller wanted" not in "\n".join(_occasion(odd))
