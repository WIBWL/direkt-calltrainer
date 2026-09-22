"""The wrap-up prompt, and F-42's phase block inside it.

Covers:
  F-09  the qualitative wrap-up asked for as structured output
  F-42  phasengerechte Sprache: the register is supposed to move warm ->
        factual -> warm again across Opening, Core Business and Closing, and
        the block that says whether it did
  ADR 0049  the model interprets, it never produces a figure
  F-10  a point names a moment by its timestamp, never by its turn id
  F-37  loudness reaches the model described rather than measured, so the
        text cannot quote a figure the chart deliberately does not show
  ADR 0004 / ADR 0051  no score, and no figure judged against a norm

Asserts the text handed to the model and the shape of the answer it is asked
for -- not what the model then does with it, which is the distinction
tests/README.md draws for every prompt test in this suite.

F-42 is the newest part of that prompt and the part with the most ways to go
wrong: the block has to name all three phases, has to give the closing more
room than the middle (the peak-end effect the feature rests on), and must not
quietly turn into the score ADR 0004 rules out.

No database and no network: `_messages` is a pure function, `_Wrapup` is a
pydantic model, and the two tests that reach `_ask`/`_strip_reasoning` stub or
bypass the model call.
"""

from types import SimpleNamespace

import pytest

from backend.clients.llm import _strip_reasoning
from backend.db import models as db_models
from backend.db.seed_data import FOCUS_GOALS
from backend.feedback import metrics
from backend.feedback.generator import (
    _ask, _dossier, _goal_without_criterion, _in_language, _LANGUAGE_NAMES_EN,
    _messages, _NO_WRAPUP, _NOTHING_SAID, _occasion, _SETTLEMENT_MARKER,
    _unfenced_text, _without_turn_markers, _Wrapup,
)
from backend.session.language_packs import LANGUAGE_PACKS

# The prompt builder and the response model are the units under test.
# pylint: disable=protected-access,redefined-outer-name


@pytest.fixture
def system_prompt() -> str:
    """The system half of the wrap-up prompt, for an otherwise empty call."""
    return _messages("Transcript, timestamped from the start of the call:", "German")[0][
        "content"
    ]


def test_prompt_names_the_three_phases(system_prompt: str) -> None:
    """F-42: the model has to be told what the phases are before it can place
    an utterance in one. Naming them is the whole input to that judgment —
    nothing upstream segments the call."""
    assert "Opening:" in system_prompt
    assert "Core business:" in system_prompt
    assert "Closing:" in system_prompt


def test_prompt_states_the_register_each_phase_calls_for(system_prompt: str) -> None:
    """The point of the feature is the switch, not the phases: a call held in
    one register throughout is what it exists to catch, so the prompt has to
    say what the movement is."""
    assert "warm, then factual, then warm again" in system_prompt
    assert "stays in a single register" in system_prompt


def test_prompt_gives_the_closing_the_most_room(system_prompt: str) -> None:
    """The peak-end effect, translated into the only currency this feature has.
    ADR 0004 leaves no score to weight, so the closing is weighted in text:
    more of the paragraph, and first claim on the suggestion."""
    assert "Give the closing more of your text than the other two phases" in system_prompt


def test_phase_block_stays_off_the_score_ladder(system_prompt: str) -> None:
    """ADR 0004/0051: describing a register is allowed, grading one is not —
    and a new block is exactly where a smuggled-in score would appear."""
    assert "never grade the call (N1)" in system_prompt
    assert "N1. No score, grade, rating, percentage, or star" in system_prompt


def test_prompt_asks_for_six_keys_including_the_phase_and_tone_blocks(
    system_prompt: str,
) -> None:
    """The keys are identifiers on the wire (protocol.ts reads `phase_language`
    and `tone_fit`), so each is named in the rule, in the shape, and in the
    closing reminder: the three places a small model reads a key name from.

    `pressure_turns` (ADR 0081) is the sixth and the only one nobody reads: it
    decides which exchanges the segment measurements are computed over.
    """
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
    """The summary and the phase paragraph say it in words.

    The wrap-up used to drop measured values into both, usually in brackets
    after the statement they were meant to support ("sachlich (62 %)"). Every
    one of those figures already stands on the same screen, in the Kennzahlen
    grid, next to what it was measured from and to the scale it belongs to; in
    a sentence it has none of that and reads as the verdict on the call that
    F2 forbids in the next line.

    Pinned by rule number and by the ban itself, not by the whole wording: the
    two blocks are prose, and the sentence explaining why may be reworded.
    """
    assert "F5. The summary and the phase_language block carry no figures" in system_prompt
    assert "never one in brackets after a statement" in system_prompt
    assert "H8. No figures in this block either" in system_prompt
    # And the silent check at the end asks for it again, which is the one the
    # model actually runs over its own answer.
    assert "neither the summary nor phase_language" in system_prompt


def test_the_tone_block_starts_from_the_occasion_and_not_from_the_figures(
    system_prompt: str,
) -> None:
    """The whole point of the block. Asked the other way round the model reads
    a figure, calls it lively, and decides afterwards what call it must have
    been -- which is the invented norm ADR 0051 refused, with a story on top."""
    assert "# The tone_fit block" in system_prompt
    assert "G1. Start from the occasion, not from the figures." in system_prompt
    assert "the quotation is what carries the observation" in system_prompt


def test_the_tone_block_rules_out_a_correct_register_for_a_kind_of_call(
    system_prompt: str,
) -> None:
    """The failure mode that would make this block a norm by the back door: two
    people handle the same complaint well sounding quite different, and a model
    left to itself will happily say what a complaint 'should' sound like."""
    assert "There is no correct register for a kind of call" in system_prompt
    assert "Do not manufacture a mismatch" in system_prompt


def test_the_tone_block_is_kept_apart_from_the_phase_block(system_prompt: str) -> None:
    """Two paragraphs about how somebody sounded, written in one call, will
    collapse into each other unless the difference is stated: one is a change
    across the call, the other is the call against its occasion."""
    assert "Do not repeat the phase_language block" in system_prompt


def test_the_dossier_names_the_occasion_before_the_statistics() -> None:
    """tone_fit cannot be answered without it. Until this block existed the
    wrap-up saw only the transcript and had to guess what kind of call it was,
    and a guess is the one thing this judgement must not rest on."""
    dossier, _ = _dossier(_session_with())

    assert "The occasion of this call" in dossier
    assert "line that has been down since Monday" in dossier
    assert "Get a repair date" in dossier, "what the caller wanted is the occasion"
    assert dossier.index("The occasion") < dossier.index("Measured statistics")


def test_the_prompt_lists_every_focus_goal_key_it_may_assign(system_prompt: str) -> None:
    """A key the model has not been shown is a key it will invent, and an
    invented key is dropped at storage time, so the point silently stops being
    countable. The catalogue is written out from the same list that seeds the
    table (`seed_data.FOCUS_GOALS`), so the two cannot drift."""
    for goal in FOCUS_GOALS:
        assert f"    {goal['id']}: {goal['title']}" in system_prompt

    assert '"goal": "<one key from the list, or an empty string>"' in system_prompt


def test_an_empty_goal_is_offered_as_a_normal_answer(system_prompt: str) -> None:
    """The rule that keeps the counts clean. A key that nearly fits puts a
    point into somebody's tally of a weakness they do not have, which is worse
    than an untagged point."""
    assert "A4. Write an empty string when nothing on the list fits" in system_prompt
    assert "Never force a fit" in system_prompt


def test_the_goal_may_not_change_what_a_point_says(system_prompt: str) -> None:
    """The failure that would make this feature actively harmful: a model that
    reaches for a key first and then writes a point to match it produces
    feedback about the catalogue rather than about the call."""
    assert "A5. The goal never changes what the point says" in system_prompt
    assert "delete the key instead" in system_prompt


def test_the_habit_goals_are_ruled_out_in_the_prompt(system_prompt: str) -> None:
    """Neither is anything one call can show. The storage side enforces it too
    (`generator._NEVER_ASSIGNED`), because a rule the model can ignore is not a
    constraint."""
    assert "Never assign either." in system_prompt


def test_the_dossier_withholds_the_success_condition() -> None:
    """It says what would have ended the call well, which is a result and not
    an occasion. Handed over, it invites the model to grade the outcome under
    the heading of tone (ADR 0079).

    Read off the Scenario the fixture actually carries. `success_condition` was
    its own column when this was written and the test asserted against an
    attribute of that name -- which migration `3ce81b27af40` merged into
    `call_goal` and `_dossier` therefore cannot read. The assertion held for
    the wrong reason, while the criterion itself was going into the dossier
    inside the goal, which is the state it was written to prevent.
    """
    dossier, _ = _dossier(_session_with())

    assert "The matter is settled when" not in dossier
    assert "named engineer" not in dossier
    # And the half in front of it is still there: the criterion is cut off the
    # goal, not the goal dropped. A wrap-up left to guess the occasion again is
    # the state the block was written to end.
    assert "Get a repair date" in dossier


def test_prompt_forbids_markup_inside_the_phase_paragraph(system_prompt: str) -> None:
    """It is rendered as a single <p> in FeedbackView, so a heading or a bullet
    would arrive as literal characters on the screen."""
    assert "no headings, no bullet characters, no line breaks" in system_prompt


def test_answer_carrying_the_phase_paragraph_parses() -> None:
    """The happy path: the fourth key lands in the field the store writes."""
    wrapup = _Wrapup.model_validate_json(
        '{"summary": "Kurz.", '
        '"phase_language": "Im Einstieg klangen Sie warm.", '
        '"strengths": [], "improvements": []}'
    )

    assert wrapup.phase_language == "Im Einstieg klangen Sie warm."


def test_answer_dropping_the_phase_paragraph_still_parses() -> None:
    """A small model (ADR 0011) drops the newest key before it drops the old
    ones. Losing the whole wrap-up over that would be the wrong trade, so the
    field is defaulted and the block simply does not appear."""
    wrapup = _Wrapup.model_validate_json(
        '{"summary": "Kurz.", "strengths": [], "improvements": []}'
    )

    assert wrapup.phase_language == ""


def test_narrative_fallback_carries_no_phase_text() -> None:
    """ADR 0049's degradation path: an answer that never validates yields the
    prose alone. It has no phase analysis in it, and must not claim one."""
    assert _Wrapup(summary="Freitext ohne JSON.").phase_language == ""


def test_every_supported_language_has_a_name_for_the_prompt() -> None:
    """ADR 0043. The prompt is English and names the language the wrap-up is to
    be written in, so every language a Persona can speak needs an entry here.

    Asserted against LANGUAGE_PACKS, the set a Persona's `language_code` is
    resolved through, so a pack added without a name fails here rather than
    reaching the model as a bare code.
    """
    assert set(LANGUAGE_PACKS) <= set(_LANGUAGE_NAMES_EN)


def test_the_language_name_is_what_the_model_is_told_to_write_in() -> None:
    """The name is interpolated into the output rules, not just stored."""
    system = _messages("dossier", _LANGUAGE_NAMES_EN["en"])[0]["content"]

    assert "Every value you write is in English" in system


async def test_the_wrapup_is_asked_in_thinking_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """ADR 0011/0043: paragraphs of German prose from an English brief on a 4B
    model, where a single pass loses agreement and word order.

    Asserted on the call, not the output -- what the trace does to the German is
    the one thing a test cannot check.
    """
    calls: list[dict] = []
    # Tells "left at llm.complete's default" apart from "explicitly None",
    # which is what the PDF summary passes and this call must not.
    unset = object()

    async def fake_complete(messages, *, max_tokens=unset, think=False):
        calls.append({"messages": messages, "max_tokens": max_tokens, "think": think})
        return '{"summary": "Kurz.", "phase_language": "", "strengths": [], "improvements": []}'

    monkeypatch.setattr("backend.clients.llm.complete", fake_complete)

    await _ask("Transcript, timestamped from the start of the call:", "German")

    assert len(calls) == 1, "one attempt is enough when the answer validates"
    assert calls[0]["think"] is True
    # The wrap-up keeps the cap; only the PDF summary (F-58) drops it, having a
    # character cap instead. Uncapped, a trace could run to the job timeout.
    assert calls[0]["max_tokens"] is unset
    assert "Transcript" in calls[0]["messages"][1]["content"]


def test_an_unfinished_reasoning_trace_yields_no_answer() -> None:
    """A `<think>` that never closes means the budget ran out mid-trace, so
    nothing after it was written.

    Returning the trace would be worse than nothing: `_unwrap` scrapes the first
    `{` out of the reply, and a trace deliberating about JSON is full of them --
    the model's reasoning would be stored and shown as its feedback.
    """
    assert _strip_reasoning("<think>Let me consider {\"summary\": ...") == ""
    assert _strip_reasoning("<think>done</think>\n{\"summary\": \"Kurz.\"}") == '{"summary": "Kurz."}'


# --- F-37: what the dossier says about loudness ----------------------------


def _measurement(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    key: str, name: str, unit: str | None, value: float, detail=None,
    segment: str = db_models.SEGMENT_CALL,
):
    """One Measurement as `_dossier` reads it -- no database needed.

    `segment` carries its real default: since ADR 0081 a Session also holds
    rows measured over the demanding stretches and over the rest, and the
    dossier speaks for the whole call only. A fixture without the field cannot
    show that difference, and the dossier read all three as the call's own.
    """
    return SimpleNamespace(
        value=value,
        detail_json=detail,
        segment=segment,
        metric_type=SimpleNamespace(key=key, name=name, unit=unit),
    )


def _session_with(*measurements) -> SimpleNamespace:
    # The Scenario is stood in for as well: `_dossier` reads its `reverse` flag
    # to decide what to call the simulated side (ADR 0070) and its situation for
    # the tone_fit block. A real Session always has one -- `session.scenario_id`
    # is NOT NULL.
    #
    # `call_goal` is here although the dossier no longer reads it, and that is
    # the point: it carries the settlement criterion, and a test asserting the
    # criterion stays out needs a Scenario that actually holds one.
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
    """The stored value is a dB span (95th percentile minus 5th). Handed over
    as a number, the wrap-up quotes it as a level -- above a chart that shows
    none (ADR 0004/0051)."""
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
    """Only loudness is described: every other metric has a unit the model
    can state plainly, and ADR 0049 wants it explaining those."""
    dossier, _ = _dossier(_session_with(
        _measurement("pace", "Sprechtempo", "WPM", 132.0),
        _measurement("questions", "Fragen", "Anzahl", 4.0),
    ))

    assert "Sprechtempo: 132.0 WPM" in dossier
    assert "Fragen: 4.0 Anzahl" in dossier


def test_a_loudness_measurement_without_a_curve_adds_no_line() -> None:
    """A row whose detail was dropped leaves the block a statistic short rather
    than asserting a course nobody measured."""
    dossier, _ = _dossier(_session_with(
        _measurement("loudness", "Lautstärke", "dB", 12.3, None),
    ))

    assert "Loudness course" not in dossier
    assert "Lautstärke" not in dossier


# --- F-10: the turn id stays out of the prose ------------------------------


def test_the_prompt_forbids_the_turn_id_in_a_text_value(system_prompt: str) -> None:
    """The id belongs in the turn_id field (O3), not in the sentence the
    trainee reads, where P1 asks for the timestamp."""
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
    """N5 is a rule, and a 4B model (ADR 0011) loses rules -- so the marker
    comes back out at the write boundary, gap and all."""
    assert _without_turn_markers(written) == expected


def test_a_sentence_that_merely_reads_like_a_marker_is_left_alone() -> None:
    """Marker shapes only: cutting "in Turn 12" out of a sentence leaves it
    ungrammatical, which is worse than the marker."""
    prose = "In Turn 12 haben Sie zugehört."
    assert _without_turn_markers(prose) == prose
    assert _without_turn_markers("Bei 02:14 sagten Sie: „Moment.“") == (
        "Bei 02:14 sagten Sie: „Moment.“"
    )


# --- The sentences the model does not write --------------------------------


def test_the_sentences_written_here_follow_the_sessions_language() -> None:
    """An empty call and a model that answered with nothing usable are the two
    wrap-ups this module writes itself, and both used to be German whatever the
    Session was -- or, for the empty call, whatever English the model echoed
    back out of O5."""
    assert _in_language(_NOTHING_SAID, "German").startswith("In diesem Training")
    assert "nothing to review" in _in_language(_NOTHING_SAID, "English")
    assert _in_language(_NO_WRAPUP, "German").startswith("Für dieses Gespräch")
    assert _in_language(_NO_WRAPUP, "English").startswith("No feedback")


def test_a_language_without_a_sentence_gets_the_german_one() -> None:
    """A KeyError here would fail the job on the one screen whose whole purpose
    is to say why there is nothing to read. German is what the pilot runs in."""
    assert _in_language(_NOTHING_SAID, "Finnish") == _in_language(_NOTHING_SAID, "German")


def test_only_the_whole_calls_statistics_reach_the_dossier() -> None:
    """The block is headed "for this call" and rule M3 tells the model to treat
    what is in it as established fact.

    Since ADR 0081 a Session also carries the same metrics measured over the
    demanding stretches and over the rest. Unfiltered, a regenerated wrap-up
    read one metric three times with three different values -- the segment rows
    are written by the previous run and are still there on the next one.
    """
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
    """The segment rows carry a `curve_db` of their own. Taking the first match
    described the pressing stretch's course as the conversation's."""
    session = _session_with(
        _measurement("loudness", "Lautstärke", "dB", 9.0,
                     detail={"curve_db": [40.0] * 30}, segment=db_models.SEGMENT_PRESSURE),
        _measurement("loudness", "Lautstärke", "dB", 12.0,
                     detail={"curve_db": [70.0] * 30}),
    )

    dossier, _ = _dossier(session)

    assert metrics.describe_loudness_course([70.0] * 30) in dossier


def test_a_reply_that_never_validated_is_not_shown_as_the_summary() -> None:
    """ADR 0049's degraded path is "a summary with no evidence links" -- the
    prose the model wrote, without its structure.

    An answer that fails to validate is very often not prose at all: JSON cut
    off in the token budget, or a field of the wrong type. Stored raw, that
    reached the User as their summary, and `scripts/requeue_feedback.py` skips
    a Session that already has a Feedback row, so it could never be replaced.
    """
    cut_off = '{"summary": "Sie haben klar nachgefragt.", "phase_language": "Sach'

    assert _unfenced_text(cut_off, "German") == _NO_WRAPUP["German"]
    assert _unfenced_text('["Klare Nachfrage."]', "German") == _NO_WRAPUP["German"]


def test_real_prose_still_becomes_the_fallback_summary() -> None:
    """The other side, so the guard cannot simply swallow every fallback: what
    ADR 0049 asks to keep is kept."""
    prose = "Sie haben ruhig und klar nachgefragt, und das Gespräch blieb sachlich."

    assert _unfenced_text(prose, "German") == prose


def test_every_seeded_goal_marks_where_its_criterion_starts() -> None:
    """The split rests on a seed convention, so the seed has to keep it.

    `_goal_without_criterion` cuts the goal at "The matter is settled when",
    which is how all 17 shipped Scenarios mark the half ADR 0079 withholds.
    Reword one without the sentence and its criterion goes back into the
    dossier, silently -- which is exactly how it got there in the first place,
    when migration 3ce81b27af40 merged the two columns.
    """
    from backend.db.seed_data import SCENARIOS  # pylint: disable=import-outside-toplevel

    missing = [s["id"] for s in SCENARIOS if _SETTLEMENT_MARKER not in s["call_goal"]]

    assert not missing, f"call_goal without the settlement sentence: {missing}"


def test_an_authored_goal_with_no_criterion_goes_in_whole() -> None:
    """A User's own Scenario carries no such sentence, and there is nothing in
    it to withhold: the goal is the occasion and all of it is."""
    own = SimpleNamespace(call_goal="Klären, ob die Lieferung diese Woche noch kommt.")

    assert _goal_without_criterion(own) == "Klären, ob die Lieferung diese Woche noch kommt."


def test_a_goal_that_is_only_a_criterion_adds_no_line() -> None:
    """Nothing is written rather than an empty label."""
    odd = SimpleNamespace(
        description="Eine Situation.",
        call_goal=f"{_SETTLEMENT_MARKER} the date is confirmed.",
        reverse=False,
    )

    assert _goal_without_criterion(odd) == ""
    assert "What the caller wanted" not in "\n".join(_occasion(odd))
