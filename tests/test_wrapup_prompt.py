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

No database and no network: `_messages` is a pure function, `_Wrapup` is a
pydantic model, and the two tests that reach `_ask`/`_strip_reasoning` stub or
bypass the model call.
"""

import pytest

from backend.clients.llm import _strip_reasoning
from backend.feedback.generator import _ask, _LANGUAGE_NAMES_EN, _messages, _Wrapup
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
