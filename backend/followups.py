"""The next call in the same matter, drafted from a Session's Feedback (F-60, ADR 0069).

Asked for via `POST /api/sessions/{id}/follow-up`; drafted here, stored by `library.py`.
The played case's four prompt fields go into the prompt (ADR 0070's exception to ADR
0043), statistics stay out (ADR 0051), and the exercise's purpose stays out of the case."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from backend.authored_text import WIRE_FIELD_LIMITS, clean, fit
from backend.clients import llm

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlayedCall:
    """The call a follow-up continues, as the prompt needs it -- one type so this
    module stays the only place that decides what a draft is built from."""

    scenario_name: str
    scenario_teaser: str
    description: str = ""
    case_facts: str = ""
    call_goal: str = ""
    # The wrap-up's summary: where that call actually ended up, which is what
    # the next one has to start from.
    outcome: str = ""
    improvements: tuple[str, ...] = ()
    phase_language: str | None = None


class FollowUpError(RuntimeError):
    """The model answered, but never with a scenario worth storing."""


# The fields `ScenarioInput` requires of a User (the three case fields may be
# empty, ADR 0045). A draft missing one of them is not a Scenario, and storing
# it would put a row in the library that POST /api/scenarios would have refused.
_REQUIRED = ("name", "short_description", "description")


class _Draft(BaseModel):
    """The six authorable fields (`backend/api/scenarios.py`'s ScenarioInput).

    All defaulted, so a missing optional key costs only that field. `_REQUIRED`
    is checked after cleaning, since a field can clean to nothing.
    """

    name: str = ""
    short_description: str = ""
    briefing: str = ""
    description: str = ""
    case_facts: str = ""
    call_goal: str = ""

    def sanitised(self) -> dict[str, str]:
        """Cleaned and capped to what the authoring API enforces (ADR 0059/0063),
        so the editor shows exactly the text that would be stored."""
        return {
            field: fit(clean(getattr(self, field)), cap)
            for field, cap in WIRE_FIELD_LIMITS.items()
        }


# --- Prompt ---------------------------------------------------------------


def _material(call: PlayedCall) -> str:
    """What the model is given: the case as it was played, and what to train."""
    lines = [
        "The call the trainee has just had:",
        f"    {call.scenario_name} -- {call.scenario_teaser}",
        "",
        "The case that was played, as the caller had it:",
    ]
    # Each of the four may be empty -- ADR 0045 lets an authored Scenario leave
    # them so. A missing line is better than a labelled blank the model fills in.
    lines += [
        f"    {label}: {text}"
        for label, text in (
            ("Situation", call.description),
            ("Facts", call.case_facts),
            ("What the caller wanted, and what settled it", call.call_goal),
        )
        if text
    ]
    if call.outcome:
        lines += ["", "Where that call ended up:", f"    {call.outcome}"]
    lines += ["", "What their coach asked them to work on, quoting that call:"]
    lines += [f"    - {text}" for text in call.improvements]
    if call.phase_language:
        lines += [
            "",
            "The coach's note on how their register moved through the call:",
            f"    {call.phase_language}",
        ]
    return "\n".join(lines)


def _messages(material: str) -> list[dict[str, str]]:
    """The prompt. English per ADR 0043; the draft itself is German.

    Numbered because a small model (ADR 0011) loses mid-paragraph rules; the ones
    it breaks otherwise are S1, S2 and S5.
    """
    caps = ", ".join(f"{field} {cap}" for field, cap in WIRE_FIELD_LIMITS.items())
    system = (
        "# Role\n"
        "You design one exercise for a telephone-training tool. A trainee has "
        "just finished a practice call and been given coaching feedback on it. "
        "Your job is to write the *next* call in that same matter: the case "
        "they played, some time later, built so that the thing the feedback "
        "asked for is the only way through it.\n"
        "\n"
        "# The material\n"
        "You are given the case as the caller had it, where that call ended "
        "up, and what the coach asked the trainee to work on. The case is "
        "yours to carry forward -- not to replace, and not to play again "
        "unchanged.\n"
        "\n"
        "# How the scenario is used\n"
        "The tool plays the caller and the trainee answers the phone. Three "
        "of the fields you write -- description, case_facts, call_goal -- are "
        "handed to the model that plays that caller, as its briefing. The "
        "other three -- name, short_description, briefing -- are read by the "
        "trainee before they start and never by the "
        "caller.\n"
        "\n"
        "# Rules for the caller's briefing\n"
        "S1. Write it entirely from the caller's side, addressed to the caller "
        'as "you". The trainee is never addressed, never described, and never '
        "referred to as a trainee: to the caller they are simply whoever picks "
        "up the phone.\n"
        "S2. Never mention feedback, coaching, training, practice, or what is "
        "being worked on, and never name the weakness. The caller may refer to "
        "the earlier call as their own -- they made it, and it is part of the "
        "case -- but never to it as an exercise. A caller who knows what the "
        "exercise is about gives the answer away, and these four fields are "
        "the caller's to read.\n"
        "S3. The facts are about the case, never about the caller: no name, no "
        "employer, no personality, no motive. Any character has to be able to "
        "carry them.\n"
        "S4. call_goal is what the *caller* wants out of this call. What the "
        "trainee ought to do is not part of it.\n"
        "S5. Carry the case forward: the same matter, a later call. Keep its "
        "anchors -- the product or contract, the figures, the dates, the names "
        "of things -- and move them on: what was agreed last time, what has "
        "happened since, what is still open. A call that repeats the first one "
        "is not an exercise, and a different matter is not this one.\n"
        "S6. call_goal says both what the caller wants and the bar they hold: "
        "what has to have happened before they consider the matter settled. "
        "That bar is where the exercise lives. Set it at exactly the thing the "
        "feedback says the trainee did not do, stated as the caller's own "
        "requirement, and set it so a vague or evasive answer does not clear it.\n"
        "S7. description is the situation in one or two sentences: who is "
        "calling, and what has brought them back. Not the facts -- those are "
        "case_facts. A description that repeats them is read out as the "
        "opening line, and a caller who recites their whole case in the first "
        "breath is the one thing that never happens on a real call.\n"
        "\n"
        "# Rules for what the trainee reads\n"
        "C1. name: a short, plain title for the situation this time. It may "
        "read as the later call in a matter that was already started; no "
        "numbering, no colon-prefix.\n"
        "C2. short_description: one short sentence for the trainee, on what "
        "this call will demand of them. At most 100 characters -- roughly "
        "twelve German words -- because it is a teaser on a selection card, "
        "not a summary; count them before you answer. Anything longer is cut "
        "off mid-sentence. The situation itself belongs in description, which "
        "has five times the room. This and briefing are the two places where "
        "the purpose of the exercise may be said out loud -- the caller reads "
        "neither.\n"
        "C3. briefing: the trainee's own side of the case, in three short "
        'sentences addressed to them as "Sie". Say exactly three things and '
        "stop: the role they answer the phone in, the room they have (what "
        "they may offer, promise or escalate), and what counts as a good "
        "outcome. Never what to say or in which order -- told that, they read "
        "a script instead of holding a conversation. It has to agree with "
        "the bar inside call_goal: never offer them something the caller "
        "would not accept, or the call cannot be won.\n"
        "\n"
        f"{llm.JSON_ANSWER_NEVER}"
        "\n"
        "# Output\n"
        "Answer with a single JSON object and nothing else.\n"
        "O1. Exactly these six keys, spelled exactly like this, all six "
        "always present: name, short_description, briefing, description, "
        "case_facts, call_goal. The keys are identifiers: "
        "never translate them, never add one.\n"
        "O2. Every value is written in German. The keys stay as they are."
        ' German is written with its own letters: "ä", "ö", "ü" and "ß", never '
        '"ae", "oe", "ue" or "ss" -- a title reading "Rueckfrage" is wrong '
        'where "Rückfrage" is the word.'
        "\n"
        "O3. Maximum lengths, in characters -- a value over its limit is cut "
        f"off, so stay under it: {caps}.\n"
        "\n"
        "Shape:\n"
        '{"name": "short title of the situation", '
        '"short_description": "one sentence to the trainee about what this call '
        'will demand of them", '
        '"briefing": "three sentences to the trainee: the role they answer '
        'in, the room they have, and what a good outcome is", '
        '"description": "the situation this time, told to the caller: who '
        'they are calling and what has happened since", '
        '"case_facts": "the concrete facts of the case, as short plain lines", '
        '"call_goal": "what the caller wants out of the call, and what has '
        'to have happened before they consider it settled"}\n'
        "\n"
        "# Before you answer, check silently\n"
        "The three caller fields say nothing about feedback, training or what "
        "is being practised; nothing in them addresses the trainee; the case is "
        "the one you were given, carried forward rather than repeated or "
        "swapped for another; description is one or two sentences and states no "
        "fact that case_facts already carries; the bar in call_goal is one a "
        "vague answer would fail; and the room briefing gives the trainee is "
        "room the caller would actually accept.\n"
        "\n"
        "The six keys stay in English. Every value is written in German. Your "
        "entire answer is the JSON object, starting with { and ending with }."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": material},
    ]


# --- Model call -----------------------------------------------------------


async def draft_follow_up(call: PlayedCall) -> dict[str, str]:
    """One draft, cleaned and capped, ready to store (thinking mode, ADR 0011).

    Propagates OpenAIError; raises FollowUpError when nothing usable came back.
    Both become a 503. Own retry loop rather than `llm.complete_json`: it also
    re-asks when required fields came back *empty*, not only on a parse failure."""
    messages = _messages(_material(call))
    for attempt in range(2):  # initial attempt + one retry
        raw = await llm.complete(
            messages,
            # No cap: the fields are bounded by their own limits, and the
            # thinking trace needs whatever room it takes.
            max_tokens=None,
            think=True,
        )
        try:
            draft = _Draft.model_validate_json(llm.json_object(raw)).sanitised()
            if all(draft[field] for field in _REQUIRED):
                return draft
            raise ValueError(f"empty {[f for f in _REQUIRED if not draft[f]]}")
        except (ValidationError, ValueError) as e:
            logger.warning("Follow-up draft did not validate (attempt %d): %s", attempt + 1, e)
    raise FollowUpError("the model produced no usable scenario draft")
