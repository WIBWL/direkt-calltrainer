"""The briefing a User reads while playing a reverse (F-61, ADR 0070).

A reverse replays one finished Session with the roles swapped, and the User
walks into it holding what the Persona held: the situation, the facts of the
case, what the caller wants, and the bar the caller counts as settled. Those
four exist already — they are the Scenario's prompt fields — but they are
written in English, addressed to whoever is playing the caller, and phrased as
instructions to a model. This module turns them into German prose addressed to
the User, and adds the short checklist of goals — the concrete things to
raise, ask and come away with — that the caller is working through.

It **translates and re-addresses; it does not invent**. That is the whole brief
the model is given, and the reason: the User is about to argue this case, so a
briefing that adds a figure the Scenario never carried would send them into the
call defending something the Persona has never heard of.

Two things stay out of it. The measured statistics, for ADR 0051's reason — no
target range exists, so nothing here can say what a figure should have been.
And the briefing never reaches any prompt: it is stored on the Scenario row and
sent to the browser, and `session/prompting.py` builds the call from the
Scenario's own fields as always. A briefing the Persona could read would be a
briefing the Persona could act on.

Unlike `backend/followups.py` this is not stateless — the result is stored, by
`library.create_reverse`, because a reverse is a Scenario the User can select
again. What the two do share is the shape, and share literally: both go through
`llm.complete_json`, which owns the thinking mode, the single retry and the
"nothing parsed" answer (ADR 0011).
"""
from __future__ import annotations

import logging

from pydantic import BaseModel

from backend.authored_text import clean
from backend.clients import llm

logger = logging.getLogger(__name__)

# How much of each field is kept. Not `authored_text.FIELD_LIMITS`: those are
# what the *authoring* API accepts into a Scenario column, and these are panels
# on a screen, sized by what stays readable beside a running call. The goals are
# short on purpose -- a list nobody can hold in their head while talking is
# decoration, and this one is meant to be glanced at and ticked off mid-call.
FIELD_LIMITS = {
    "situation": 600,
    "facts": 1500,
    "goal": 400,
    "settled": 400,
}
GOAL_LIMIT = 120
MAX_GOALS = 5


class ReverseError(RuntimeError):
    """The model answered, but never with a briefing that parsed."""


class _Brief(BaseModel):
    """The briefing panel's fields.

    All defaulted, like the follow-up's draft: a missing key costs that panel,
    not the whole briefing. A reverse with a thin brief is still a usable
    exercise — the case is in the Scenario either way — where no reverse at all
    is not.
    """

    situation: str = ""
    facts: str = ""
    goal: str = ""
    settled: str = ""
    goals: list[str] = []

    def sanitised(self) -> dict:
        """Cleaned (ADR 0059) and capped, ready to store and to show.

        Run through `clean` for the same reason authored text is, even though
        this text never reaches a prompt: it is stored on a Scenario row, and
        the rule that keeps control tokens out of that table should not depend
        on which writer filled the row in.
        """
        brief = {
            field: clean(getattr(self, field))[:cap] for field, cap in FIELD_LIMITS.items()
        }
        goals = [clean(g)[:GOAL_LIMIT].strip() for g in self.goals]
        brief["goals"] = [g for g in goals if g][:MAX_GOALS]
        return brief


# --- Prompt ---------------------------------------------------------------


def _material(
    description: str,
    case_facts: str,
    call_goal: str,
    success_condition: str,
    improvements: list[str],
) -> str:
    """What the model is given: the four fields to turn around, and — where a
    wrap-up exists — what the coach asked the User to work on, which decides
    the order the goals come in. A Session whose wrap-up has not landed simply
    has no such lines, and the goals are read off the case alone."""
    lines = [
        "The scenario the trainee has just played, as the simulated caller "
        "received it:",
        "",
        f"SITUATION: {description or '(none given)'}",
        f"FACTS OF THE CASE: {case_facts or '(none given)'}",
        f"WHAT THE CALLER WANTED: {call_goal or '(none given)'}",
        f"THE CALLER COUNTED IT SETTLED WHEN: {success_condition or '(none given)'}",
    ]
    if improvements:
        lines += [
            "",
            "What their coach asked them to work on, quoting that call:",
        ]
        lines += [f"    - {text}" for text in improvements]
    return "\n".join(lines)


def _messages(material: str) -> list[dict[str, str]]:
    """The prompt. English per ADR 0043; the briefing itself is German.

    Numbered and sectioned like the wrap-up's, for the same reason (ADR 0011).
    The three rules a small model breaks here are R1 (it writes a new case
    rather than translating the one it was given), R2 (it addresses the trainee
    as the person answering the phone, which is the role they are leaving) and
    G2 (it answers with advice about manner — „bleiben Sie ruhig“ — where a
    goal has to be a thing that either happened in the call or did not).
    """
    system = (
        "# Role\n"
        "You prepare a trainee for a phone-call exercise. They have just "
        "finished a practice call in which a simulated customer rang them. "
        "Now the roles are swapped: they are about to make that same call "
        "themselves, and the machine will play the company side. Your job is "
        "to hand them the briefing the simulated caller had, written for them "
        "to read while they are on the phone.\n"
        "\n"
        "# What you are given\n"
        "Four fields, written in English and addressed to whoever plays the "
        "caller, and — sometimes — the coaching points from the call they "
        "have just had.\n"
        "\n"
        "# Rules for the four fields\n"
        "R1. Translate and re-address. Every fact, figure, date and name in "
        "your answer must already be in the material. Invent nothing: they "
        "are about to argue this case, and a detail you added is one the "
        "other side has never heard of. Where a field says nothing, write "
        "that there is nothing fixed on this point rather than filling it in.\n"
        'R2. Address the trainee directly as "Sie", as the person making the '
        "call. They are the customer now. Never address them as the company, "
        "the agent, or the person answering the phone.\n"
        "R3. Say nothing about the previous call, about feedback, coaching or "
        "training, and never tell them how they did. This is a briefing for a "
        "call that has not happened yet.\n"
        "R4. Plain, short sentences, no headings and no lists inside these "
        "four fields. Each is one short paragraph.\n"
        "\n"
        "# The four fields\n"
        "situation: where you are calling from and why, in two or three "
        "sentences.\n"
        "facts: what you know about the case — the concrete points, as short "
        "plain sentences, one after another in a single paragraph. This is "
        "the field they will glance at mid-call, so keep every figure and "
        "date the material gives and drop nothing.\n"
        "goal: what you want out of this call.\n"
        "settled: what has to have happened before you consider the matter "
        "dealt with.\n"
        "\n"
        "# Rules for goals\n"
        "G1. Three to five items: the checklist of what this call has to "
        "cover. Each one is a single concrete thing to raise, to ask, or to "
        "come away with — a point to put on the table, a question to get an "
        "answer to, a commitment to obtain. Together they are the caller's "
        "agenda, in the order it makes sense to work through them.\n"
        "G2. Each has to be tickable: once the call is over it must be plain "
        "whether it happened or not. „Lassen Sie sich ein konkretes Datum für "
        "die Gutschrift nennen“ can be ticked off; „Bleiben Sie freundlich“ "
        "and „Achten Sie auf Ihren Ton“ cannot. Never write advice about "
        "manner, tone, pace or attitude — those are not goals.\n"
        "G3. Draw them from the material and nothing else: the figures and "
        "dates in the facts that have to be said out loud, the questions the "
        "case leaves open, and the bar in the settled field, which is always "
        "among them. Invent no demand the material does not carry. Where "
        "coaching points are given, let them decide which goals come first — "
        "state each as the thing to achieve, never as a remark about how it "
        "went last time.\n"
        "G4. Short: one line each, at most about twelve words, beginning with "
        "the verb. No sub-clause explaining why it matters.\n"
        "\n"
        "# Never\n"
        "N1. No markdown, no headings, no bullet characters, no line breaks "
        "inside the JSON strings.\n"
        "N2. No straight double quote inside a string: forget the backslash "
        "in front of one and the whole answer is unreadable. Use „ “ or "
        "single quotes.\n"
        "N3. No text of any kind before or after the JSON object.\n"
        "\n"
        "# Output\n"
        "Answer with a single JSON object and nothing else.\n"
        "O1. Exactly these five keys, spelled exactly like this, all five "
        "always present: situation, facts, goal, settled, goals. The keys are "
        "identifiers: never translate them, never add one. `goal` and `goals` "
        "are two different fields: `goal` is the one sentence on what you want "
        "out of this call, `goals` is the checklist of what has to happen in "
        "it.\n"
        "O2. Every value is written in German, and goals is a list of German "
        "strings. The keys stay as they are.\n"
        "\n"
        "Shape:\n"
        '{"situation": "where you are calling from and why", '
        '"facts": "what you know about the case, as short plain sentences", '
        '"goal": "what you want out of this call", '
        '"settled": "what has to have happened before it is dealt with", '
        '"goals": ["one thing to raise, ask or obtain", "another"]}\n'
        "\n"
        "# Before you answer, check silently\n"
        "Every fact in your answer is in the material; the trainee is "
        'addressed as the person making the call; nothing refers to an '
        "earlier call, to feedback or to training; and every goal is a "
        "concrete thing to raise, ask or obtain that can be ticked off once it "
        "has happened, never a remark about how to behave.\n"
        "\n"
        "The five keys stay in English. Every value is written in German. "
        "Your entire answer is the JSON object, starting with { and ending "
        "with }."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": material},
    ]


# --- Model call -----------------------------------------------------------


async def draft_brief(
    description: str,
    case_facts: str,
    call_goal: str,
    success_condition: str,
    improvements: list[str] | None = None,
) -> dict:
    """One briefing, cleaned and capped, ready to store on the reverse.

    Thinking mode and one retry, as off the live path (ADR 0011) --
    `llm.complete_json` owns both, so the follow-up draft (F-60) and this one
    cannot drift apart on how hard they try. Propagates OpenAIError; raises
    ReverseError when nothing parsed. Unlike the wrap-up there is no narrative
    fallback worth keeping: the reverse would be created either way, and a
    Scenario carrying an unreadable briefing is worse than a button that says
    to try again.
    """
    messages = _messages(
        _material(description, case_facts, call_goal, success_condition, improvements or [])
    )
    brief = await llm.complete_json(messages, _Brief, "Reverse briefing")
    if brief is None:
        raise ReverseError("the model produced no usable briefing")
    return brief.sanitised()
