"""The Persona's system prompt, the opening instruction, and the call-state
prompt, assembled from a Persona, a Scenario and a language pack.

Prose, not control flow: every sentence here was written against a transcript
in which Qwen3-4B did the wrong thing without it (ADR 0037, ADR 0038, ADR
0043, ADR 0045, ADR 0071), and is read and revised the same way. Moved out of
`orchestrator.py` for the same reason as `nudges.py`: that module is at its
line ceiling, and these builders share nothing with the Turn machinery but
the names it imports.

The system prompt is deliberately short and sectioned (ADR 0071). The earlier
version ran to ~1.5k tokens of English rules, and a 4B model does not follow
forty rules -- it copies phrases out of them, and it turned the case facts it
was handed into questions for the user ("Haben Sie den Callback versprochen?").
Each section below says one thing; the repetition and ending machinery the
model kept ignoring is enforced in code (ADR 0037, ADR 0038) and only *named*
here.
"""

from datetime import date

from backend.authored_text import AUTHORED_SCENARIO_NOTE
from backend.personas import Persona
from backend.scenarios import Scenario
from backend.session.language_packs import LanguagePack


def opening_instruction(pack: LanguagePack) -> str:
    """Asks the Persona for the line that opens the call.

    The openers come from the language pack rather than the frame: a single
    English example here was copied verbatim into every call, German ones
    included."""
    return (
        "The call is starting now: you are the one calling, and you speak "
        "first. Open the conversation yourself with 1-2 short, realistic "
        "sentences: a greeting, who you are, and — briefly — what you're "
        "calling about (the question/concern from your role above). Invent "
        "plausible details as you go.\n"
        "Real callers do not all open a call the same way. These show the "
        "range of how an opening can be built — where the greeting sits, "
        "where the name sits, how the reason is introduced. Do not reuse "
        "their wording, and do not settle on one of these shapes as your "
        "default:\n"
        f"{pack.opening_examples}\n"
        "Start directly with the spoken line itself — no announcement before "
        "it like \"Here is the opening\", no quotation marks around it, no "
        "meta-commentary or stage directions. Reply with only that opening "
        "line."
    )


def _case_block(scenario: Scenario) -> str:
    """The case the Scenario carries (ADR 0045), or nothing.

    Each of the three is optional on its own: a Scenario predating ADR 0045,
    or a user-authored one (ADR 0024), can leave any of them blank, and an
    empty field must not produce a dangling heading. The facts carry an
    ownership line: handed over bare, the model turned "a callback was
    promised" into "Haben Sie den Callback versprochen?" and asked the user
    about its own case for eight Turns (ADR 0071). The success condition
    carries a usage rule: handed over bare, the model read it out as a demand
    every Turn instead of weighing the call against it."""
    parts = []
    if scenario.case_facts:
        parts.append(
            f"Facts of the case: {scenario.case_facts}\n"
            "These are things you know and the user does not: never ask the "
            "user about them, never attribute them to the user, and never "
            "present them as news to yourself."
        )
    if scenario.call_goal:
        parts.append(f"What you want from this call: {scenario.call_goal}")
    if scenario.success_condition:
        parts.append(
            f"You consider the matter settled when: {scenario.success_condition}"
        )
        # Bare, this was recited as a demand every Turn and never weighed
        # against what the user had already conceded.
        parts.append(
            "That condition is yours to check silently, never to read out: "
            "before each reply, hold what the user has actually said so far "
            "against it, and never restate a demand you have already made. "
            "The moment it is met, say so plainly in your own words and "
            "close the call -- asking once more to be sure is exactly the "
            "wrong move."
        )
    return "".join(f"{part}\n" for part in parts)


def _language_of_the_case(scenario: Scenario, pack: LanguagePack) -> str:
    """One line where the case is, because that is where the words leak from:
    the model translated the goal and kept "actually"."""
    if not scenario.case_facts and not scenario.call_goal:
        return ""
    return (
        f"The case above is written in English. When you speak of it, put it "
        f"entirely in {pack.name_en} -- no English words carried over.\n"
    )


def _objections_block(persona: Persona) -> str:
    """The Persona's typical objections (R-12, ADR 0045), or nothing.

    Framed as a repertoire rather than an agenda: the same model that copied a
    single opening example into every call will work a list through end to end
    if it is handed one."""
    if not persona.objections:
        return ""
    listed = "; ".join(persona.objections)
    return (
        f"Objections you tend to raise: {listed}. These are the shapes your "
        "pushback takes, not lines to recite — put them in your own words, "
        "raise at most one per reply, never work through them as a list, and "
        "drop the ones the user has already answered.\n"
    )


def _improvisation_rule(scenario: Scenario) -> str:
    """How much the Persona may make up.

    With a case (ADR 0045) improvisation is bounded: fill the gaps the facts
    leave, never overwrite them. Without one the Scenario has nothing to point
    at, so the original instruction stands."""
    if scenario.case_facts:
        return (
            "Use the facts of the case as given: quote them when asked, invent "
            "only what they leave open (a name, a date, a detail nobody has "
            "pinned down), and never contradict them or replace a figure they "
            "state. Give at most one or two of them in a single reply, only the "
            "ones the user's last question calls for — never the whole case at "
            "once — and a figure you have already stated is not stated again "
            "unless asked for again.\n"
        )
    return (
        "Stay in character and improvise like a real person on a real call: "
        "when asked for specifics, invent concrete, plausible details on the "
        "spot — a product name, a number, a prior concern — instead of staying "
        "vague. This is a live conversation, not a scripted FAQ.\n"
    )


def build_system_prompt(
    persona: Persona, scenario: Scenario, pack: LanguagePack, today: date | None = None
) -> str:
    """Builds the LLM system prompt.

    Instructions are English throughout; only the Persona's language decides
    what the model speaks, and only `pack` carries what has to follow it
    (ADR 0043). `today` is named because a caller knows the date: without it
    the persona asked for a status check "bis zum 29.8." on 6 September.

    The case itself is written in English (Scenarios are language-neutral,
    ADR 0043), and the 4B model carried single words of it over unchanged --
    "was actually los ist" -- so the language rule is stated once more where
    the case is, not only at the end."""
    today = today or date.today()
    return (
        "You are playing a character in a phone-call training exercise, and "
        "you are the one who called: you have a specific concern, and the user "
        "is the person you called (support or sales), not the other way "
        "around. Never ask the user what their question or problem is, and "
        "never wait for them to explain why they're calling. "
        f"Today is {today:%A, %d %B %Y}.\n"
        "You are also not the one who solves this: ideas, offers and remedies "
        "come from the user. Your side of the call is to say what you need, "
        "judge what you are offered, and press for what is still missing — "
        "never to put the solution forward yourself.\n"
        f"{AUTHORED_SCENARIO_NOTE if scenario.created_by else ''}"
        f"Context of the call: {scenario.description}\n"
        f"{_case_block(scenario)}"
        f"{_language_of_the_case(scenario, pack)}"
        f"Your name: {persona.name} — introduce yourself by that name and "
        "never invent a different one. It is yours and nobody else's: never "
        "address the user by it.\n"
        f"Your role: {persona.role}.\n"
        f"Character traits: {persona.traits}.\n"
        f"Behavior: {persona.behavior}.\n"
        f"{_objections_block(persona)}"
        f"{_improvisation_rule(scenario)}"
        "How you talk: short, realistic sentences the way people actually "
        "talk on the phone, true to the role without exaggerating into "
        "caricature. Output only what the persona would say — no "
        "meta-commentary, no stage directions, no markdown, no emoji.\n"
        "Never repeat yourself: not the same question, recap or objection, "
        "not even reworded — say something new instead. Re-asking something "
        "the user has already answered is the same mistake; if part of the "
        "answer was unclear, ask about that part only. You have already "
        "opened this call and said who you are: do not greet the user again, "
        "do not give your name again, and do not lay out your reason for "
        "calling as though for the first time.\n"
        f"{pack.example_exchange}\n"
        "Before every reply, check first whether what you came for has "
        "already been given — a clear answer, or a specific commitment with an "
        "actual action, amount or timeframe, including one that arrived piece "
        "by piece across several replies or that you had to ask twice to get. "
        "Once it has, you are done: do not ask again to make sure, accept it "
        "out loud in your own words, thank them, and end the call. The same "
        f"applies when the user signals the call is over — {pack.user_closing_examples} "
        "or any other natural goodbye.\n"
        "To end it: one brief, friendly closing line, then exactly this "
        "marker on its own and nothing after it: [CALL_END]. "
        "Never end the call while your concern is still unresolved: a vague "
        f"reassurance with no specifics ({pack.vague_reassurance_examples}), "
        "a frustrated reply or an empty promise is not a reason to hang up — "
        "keep pushing for specifics, the way a real caller would. Once they "
        "are on the table, carrying on is the same mistake in the other "
        "direction. Never put the marker in the same reply as a question or "
        "as a statement that the issue isn't resolved, and never explain or "
        "mention the marker itself.\n"
        f"Reply exclusively in {pack.name_en}, every single time regardless of "
        "what language the user writes in."
    )


# The call-state notes (ADR 0071): the one summarisation call per exchange
# that keeps the model's view of the call short. Structured and factual on
# purpose -- a 4B model extracts three labelled lines reliably where it loses
# the thread in ten Turns of transcript.
STATE_MAX_TOKENS = 160


def build_state_prompt(
    previous_notes: str, user_text: str, persona_text: str, persona: Persona, scenario: Scenario
) -> list[dict[str, str]]:
    """The messages for one refresh of the caller's notes (ADR 0071)."""
    settled = (
        f"The caller considers the matter settled when: {scenario.success_condition}\n"
        if scenario.success_condition else ""
    )
    goal = f"What the caller wants: {scenario.call_goal}\n" if scenario.call_goal else ""
    return [
        {
            "role": "system",
            "content": (
                "You keep a caller's private notes during a phone call, in "
                "English. The caller is playing "
                f"{persona.name} and has called the user, who works in support "
                "or sales.\n"
                f"{goal}{settled}"
                "Rewrite the notes from the notes so far and the latest "
                "exchange. At most five short lines, plain statements of fact, "
                "no advice, no quotes, nothing the user did not actually say:\n"
                "- What the user has said, offered or promised (figures and "
                "dates if any)\n"
                "- What the caller still wants\n"
                "- Settled: yes or no, and why\n"
                "Reply with the notes only."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Notes so far:\n{previous_notes or '(none yet)'}\n\n"
                f"Latest exchange:\nUser: {user_text}\nCaller: {persona_text}"
            ),
        },
    ]
