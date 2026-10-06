"""The follow-up draft (F-60, ADR 0069): the next call in the same matter. The
played case goes into the prompt; statistics and the exercise's purpose stay out."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from shared.clients import llm
from backend.authored_text import FIELD_LIMITS, WIRE_FIELD_LIMITS, clean, fit

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlayedCall:
    scenario_name: str
    scenario_teaser: str
    description: str = ""
    case_facts: str = ""
    call_goal: str = ""
    # Where that call ended up, which the next one starts from.
    outcome: str = ""
    improvements: tuple[str, ...] = ()
    phase_language: str | None = None


class FollowUpError(RuntimeError):
    """The model answered, but never with a scenario worth storing."""


# What POST /api/scenarios requires, plus the trainee's "Worum es geht", without
# which the panel shows the caller's "Sie rufen an" as the trainee's own.
_REQUIRED = ("name", "short_description", "description", "description_label")


class _Draft(BaseModel):
    """The authorable fields plus `situation` (stored as `description_label`).
    `_REQUIRED` is checked after cleaning, since a field can clean to nothing."""

    name: str = ""
    short_description: str = ""
    situation: str = ""
    briefing: str = ""
    description: str = ""
    case_facts: str = ""
    call_goal: str = ""

    def sanitised(self) -> dict[str, str]:
        """Capped exactly as the authoring API would store it."""
        draft = {
            field: fit(clean(getattr(self, field)), cap)
            for field, cap in WIRE_FIELD_LIMITS.items()
        }
        draft["description_label"] = fit(clean(self.situation), FIELD_LIMITS["description"])
        return draft


def _material(call: PlayedCall) -> str:
    lines = [
        "The call the trainee has just had:",
        f"    {call.scenario_name} -- {call.scenario_teaser}",
        "",
        "The case that was played, as the caller had it:",
    ]
    # An empty field is left out rather than shown as a blank the model fills.
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
    """English prompt (ADR 0043), numbered because a small model loses rules mid-paragraph."""
    limits = {**WIRE_FIELD_LIMITS, "situation": FIELD_LIMITS["description"]}
    caps = ", ".join(f"{field} {cap}" for field, cap in limits.items())
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
        "other four -- name, short_description, situation, briefing -- are "
        "read by the trainee before they start and never by the "
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
        "has five times the room. This, situation and briefing are the places "
        "where the purpose of the exercise may be said out loud -- the caller "
        "reads none of them.\n"
        "C3. situation: what the trainee is told the call is about before "
        "they pick it, in two or three sentences, written about the people "
        'rather than to them -- "der Kunde", "die Kundin", never "Sie". Say '
        "that the caller from the last call rings again and why, as far as "
        "the trainee could know it from the matter, then close with one "
        'sentence starting "Geübt wird" that names what this call practises. '
        "It is description seen from the trainee's end of the line: they are "
        "the one who is rung and picks up, never the one who calls. Never "
        'copy description, which is addressed to the caller and reads "Sie '
        'rufen an".\n'
        "C4. briefing: the trainee's own side of the case, in three short "
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
        "O1. Exactly these seven keys, spelled exactly like this, all seven "
        "always present: name, short_description, situation, briefing, "
        "description, case_facts, call_goal. The keys are identifiers: "
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
        '"situation": "for the trainee, about the people: the caller from the '
        'last call rings again, and why; then one sentence starting Geübt wird", '
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
        "is being practised; nothing in them addresses the trainee; situation "
        "has the caller ring the trainee, never the other way round; the case is "
        "the one you were given, carried forward rather than repeated or "
        "swapped for another; description is one or two sentences and states no "
        "fact that case_facts already carries; the bar in call_goal is one a "
        "vague answer would fail; and the room briefing gives the trainee is "
        "room the caller would actually accept.\n"
        "\n"
        "The seven keys stay in English. Every value is written in German. Your "
        "entire answer is the JSON object, starting with { and ending with }."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": material},
    ]


async def draft_follow_up(call: PlayedCall) -> dict[str, str]:
    """Propagates OpenAIError; FollowUpError when nothing usable came back. Its
    own retry loop, because it also re-asks on empty required fields."""
    messages = _messages(_material(call))
    for attempt in range(2):
        raw = await llm.complete(
            messages,
            # No cap: the fields bound themselves. No thinking (ADR 0103).
            max_tokens=None,
        )
        try:
            draft = _Draft.model_validate_json(llm.json_object(raw)).sanitised()
            if all(draft[field] for field in _REQUIRED):
                return draft
            raise ValueError(f"empty {[f for f in _REQUIRED if not draft[f]]}")
        except (ValidationError, ValueError) as e:
            logger.warning("Follow-up draft did not validate (attempt %d): %s", attempt + 1, e)
    raise FollowUpError("the model produced no usable scenario draft")
