"""The wrap-up prompt, and F-42's phase block inside it.

Covers:
  F-09  the qualitative wrap-up asked for as structured output
  F-42  phasengerechte Sprache: the register is supposed to move warm ->
        factual -> warm again across Opening, Core Business and Closing, and
        the block that says whether it did
  ADR 0049  the model interprets, it never produces a figure
  ADR 0004 / ADR 0051  no score, and no figure judged against a norm

Asserts the text handed to the model and the shape of the answer it is asked
for -- not what the model then does with it, which is the distinction
tests/README.md draws for every prompt test in this suite.

F-42 is the newest part of that prompt and the part with the most ways to go
wrong: the block has to name all three phases, has to give the closing more
room than the middle (the peak-end effect the feature rests on), and must not
quietly turn into the score ADR 0004 rules out.

No database and no network: `_messages` is a pure function and `_Wrapup` is a
pydantic model.
"""

import pytest

from backend.feedback.generator import _messages, _Wrapup

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


def test_prompt_asks_for_four_keys_including_the_phase_block(system_prompt: str) -> None:
    """The key is an identifier on the wire (protocol.ts reads `phase_language`),
    so it is named in the rule, in the shape, and in the closing reminder —
    the three places a small model reads a key name from."""
    assert "summary, phase_language, strengths, improvements" in system_prompt
    assert '"phase_language": "one paragraph' in system_prompt
    assert "The four keys stay in English" in system_prompt
    assert "three keys" not in system_prompt


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
