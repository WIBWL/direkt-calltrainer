"""Draft the next exercise from a Session's Feedback: a follow-up Scenario (F-60).

The improvement points say what to work on; the model is asked for a Scenario
that cannot be got through without it. Stateless like `backend/documents.py`:
the draft goes to the editor and becomes a Scenario only when the User saves it,
so sanitising, caps, ownership and the Tenant stamp stay where they are
(ADR 0064).

Withheld from the model: the measured statistics (no target range exists,
ADR 0051) and the played Scenario's prompt fields (withheld from the client
anyway, ADR 0043) -- only its card goes in. The four case fields become the
caller's briefing, so the prompt keeps the exercise's purpose out of them.

The values are German: the draft's destination is the editor, as with F-58.
"""
from __future__ import annotations

import logging

from pydantic import BaseModel, ValidationError

from backend.authored_text import WIRE_FIELD_LIMITS, clean
from backend.clients import llm

logger = logging.getLogger(__name__)


class FollowUpError(RuntimeError):
    """The model answered, but never with a draft that parsed."""


class _Draft(BaseModel):
    """The six authorable fields (`backend/api/scenarios.py`'s ScenarioInput).

    All defaulted: a missing key costs that field, not the whole draft.
    """

    name: str = ""
    short_description: str = ""
    description: str = ""
    case_facts: str = ""
    call_goal: str = ""
    success_condition: str = ""

    def sanitised(self) -> dict[str, str]:
        """Cleaned and capped to what the authoring API enforces (ADR 0059/0063),
        so the editor shows exactly the text that would be stored."""
        return {
            field: clean(getattr(self, field))[:cap] for field, cap in WIRE_FIELD_LIMITS.items()
        }


# --- Prompt ---------------------------------------------------------------


def _material(
    scenario_name: str,
    scenario_teaser: str,
    improvements: list[str],
    phase_language: str | None,
) -> str:
    """What the model is given: the played Scenario's card, and what to train."""
    lines = [
        "Subject area of the call the trainee has just had:",
        f"    {scenario_name} -- {scenario_teaser}",
        "",
        "What their coach asked them to work on, quoting that call:",
    ]
    lines += [f"    - {text}" for text in improvements]
    if phase_language:
        lines += [
            "",
            "The coach's note on how their register moved through the call:",
            f"    {phase_language}",
        ]
    return "\n".join(lines)


def _messages(material: str) -> list[dict[str, str]]:
    """The prompt. English per ADR 0043; the draft itself is German.

    Numbered, like the wrap-up's: a small model (ADR 0011) loses a rule that
    sits mid-paragraph. The ones it breaks without them are S2 (the caller must
    not learn what is being trained), S1 (no addressing the trainee) and S5
    (invent a case rather than copy the one it was given the card of).
    """
    caps = ", ".join(f"{field} {cap}" for field, cap in WIRE_FIELD_LIMITS.items())
    system = (
        "# Role\n"
        "You design one exercise for a telephone-training tool. A trainee has "
        "just finished a practice call and been given coaching feedback on it. "
        "Your job is to write the *next* scenario for them: a new call, in the "
        "same subject area, built so that the thing the feedback asked for is "
        "the only way through it.\n"
        "\n"
        "# How the scenario is used\n"
        "The tool plays the caller and the trainee answers the phone. Four of "
        "the fields you write -- description, case_facts, call_goal, "
        "success_condition -- are handed to the model that plays that caller, "
        "as its briefing. The other two -- name, short_description -- are the "
        "card the trainee reads before they start.\n"
        "\n"
        "# Rules for the caller's briefing\n"
        "S1. Write it entirely from the caller's side, addressed to the caller "
        'as "you". The trainee is never addressed, never described, and never '
        "referred to as a trainee: to the caller they are simply whoever picks "
        "up the phone.\n"
        "S2. Never mention feedback, coaching, training, practice, a previous "
        "call, or what is being worked on. Never name the weakness. A caller "
        "who knows what the exercise is about gives the answer away, and these "
        "four fields are the caller's to read.\n"
        "S3. The facts are about the case, never about the caller: no name, no "
        "employer, no personality, no motive. Any character has to be able to "
        "carry them.\n"
        "S4. call_goal is what the *caller* wants out of this call. What the "
        "trainee ought to do is not part of it.\n"
        "S5. Invent a new case: concrete figures, dates, a product or contract, "
        "what happened before this call. Do not reuse the case from the "
        "subject-area line -- you are given it to know the field, not to copy "
        "it. A scenario with no specifics plays out as small talk.\n"
        "S6. success_condition is the bar the *caller* holds: what has to have "
        "happened before they consider the matter settled. This is where the "
        "exercise lives. Set it at exactly the thing the feedback says the "
        "trainee did not do, stated as the caller's own requirement, and set it "
        "so that a vague or evasive answer does not clear it.\n"
        "\n"
        "# Rules for the card\n"
        "C1. name: a short, plain title for the situation. No colon-prefix, no "
        '"Folgegespräch", no numbering.\n'
        "C2. short_description: one sentence for the trainee, on what this call "
        "is and what it will demand of them. This is the one place where the "
        "purpose of the exercise may be said out loud -- the caller never reads "
        "it.\n"
        "\n"
        "# Never\n"
        "N1. No markdown, no headings, no bullet characters, no line breaks "
        "inside the JSON strings.\n"
        "N2. No straight double quote inside a string: forget the backslash in "
        "front of one and the whole answer is unreadable. Use „ “ or single "
        "quotes.\n"
        "N3. No text of any kind before or after the JSON object.\n"
        "\n"
        "# Output\n"
        "Answer with a single JSON object and nothing else.\n"
        "O1. Exactly these six keys, spelled exactly like this, all six always "
        "present: name, short_description, description, case_facts, call_goal, "
        "success_condition. The keys are identifiers: never translate them, "
        "never add one.\n"
        "O2. Every value is written in German. The keys stay as they are.\n"
        "O3. Maximum lengths, in characters -- a value over its limit is cut "
        f"off, so stay under it: {caps}.\n"
        "\n"
        "Shape:\n"
        '{"name": "short title of the situation", '
        '"short_description": "one sentence to the trainee about what this call '
        'will demand of them", '
        '"description": "the situation, told to the caller: who they are '
        'calling and why", '
        '"case_facts": "the concrete facts of the case, as short plain lines", '
        '"call_goal": "what the caller wants out of the call", '
        '"success_condition": "what has to have happened before the caller '
        'considers it settled"}\n'
        "\n"
        "# Before you answer, check silently\n"
        "The four briefing fields say nothing about feedback, training or what "
        "is being practised; nothing in them addresses the trainee; the case is "
        "one you invented rather than the one named in the subject area; and "
        "success_condition is a bar a vague answer would fail.\n"
        "\n"
        "The six keys stay in English. Every value is written in German. Your "
        "entire answer is the JSON object, starting with { and ending with }."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": material},
    ]


# --- Model call -----------------------------------------------------------


async def draft_follow_up(
    scenario_name: str,
    scenario_teaser: str,
    improvements: list[str],
    phase_language: str | None = None,
) -> dict[str, str]:
    """One draft, cleaned and capped, ready for the editor.

    Thinking mode, as off the live path (ADR 0011). Propagates OpenAIError;
    raises FollowUpError when nothing parsed -- unlike the wrap-up there is no
    partial result worth keeping, because an empty editor is not a draft.
    """
    messages = _messages(_material(scenario_name, scenario_teaser, improvements, phase_language))
    for attempt in range(2):  # initial attempt + one retry
        raw = await llm.complete(
            messages,
            # No cap: the fields are bounded by their own limits, and the
            # thinking trace needs whatever room it takes.
            max_tokens=None,
            think=True,
        )
        try:
            return _Draft.model_validate_json(llm.json_object(raw)).sanitised()
        except (ValidationError, ValueError) as e:
            logger.warning("Follow-up draft did not validate (attempt %d): %s", attempt + 1, e)
    raise FollowUpError("the model produced no usable scenario draft")
