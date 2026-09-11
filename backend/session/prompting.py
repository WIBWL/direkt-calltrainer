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


def opening_instruction(pack: LanguagePack, reverse: bool = False) -> str:
    """Asks the Persona for the line that opens the call.

    The openers come from the language pack rather than the frame: a single
    English example here was copied verbatim into every call, German ones
    included.

    In a reverse (ADR 0070) the Persona still speaks first, it just says less:
    it is answering a phone, so it may say who picked up and nothing else. The
    reason for the call is the User's to give, and a callee who guesses at it
    has answered the exercise before it started.
    """
    if reverse:
        return (
            "The phone is ringing and you are picking it up. Say only what "
            "someone says when they answer a call at work: a greeting, the "
            "company or department, your name, and an offer to help. One "
            "short sentence, two at the most.\n"
            "You do not know who is calling or what about. Say nothing about "
            "any case, any contract, any ticket and any previous contact, ask "
            "nothing beyond what the caller needs, and do not guess at their "
            "reason — you find that out by letting them speak.\n"
            "These show the range of how a call gets answered. Do not reuse "
            "their wording:\n"
            f"{pack.answering_examples}\n"
            "Start directly with the spoken line itself — no announcement "
            "before it, no quotation marks around it, no meta-commentary or "
            "stage directions. Reply with only that line."
        )
    return (
        "The call is starting now: you are the one calling, and you speak "
        "first. Open the conversation yourself with 1-2 short, realistic "
        "sentences: a greeting, who you are, and — briefly — what you're "
        "calling about (the question/concern from your role above). Invent "
        "plausible details as you go.\n"
        "Name the reason in a clause, not in a summary: what you want, in one "
        "breath. The background — what was agreed before, what has happened "
        "since, the figures and the dates — is yours to give when you are "
        "asked for it, one piece at a time. A caller who delivers the whole "
        "case in their opening sounds like someone reading a file out.\n"
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
    every Turn instead of weighing the call against it.

    A reverse (ADR 0070) gets the same three fields relabelled, not a second
    case: the goal and the settlement condition are the *caller's* there, and
    the caller is the User. Saying so is what stops the model from adopting
    them — handed "What you want from this call" while playing the callee, it
    started making the User's demands at the User.
    """
    if scenario.reverse:
        return _reverse_case_block(scenario)
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


def _reverse_case_block(scenario: Scenario) -> str:
    """The same case from the other side of the phone (ADR 0070).

    Each field keeps its own optionality, exactly as above. The ownership line
    turns around with the casting: what the caller must not be asked about
    becomes what is on file with you, and the settlement condition stops being
    yours to hold and becomes theirs to be met.
    """
    parts = []
    if scenario.case_facts:
        parts.append(
            f"Facts of the case, as they stand on your side: {scenario.case_facts}\n"
            "This is what your records show. Do not contradict it, do not "
            "present it as news to yourself, and do not recite it back at the "
            "caller — give the piece their last question actually calls for."
        )
    if scenario.call_goal:
        parts.append(
            f"What the caller wants from this call: {scenario.call_goal}\n"
            "That is their goal and not yours: never state it as your own "
            "reason for calling, and never ask them to do it for you."
        )
    if scenario.success_condition:
        parts.append(
            "The caller will count the matter as settled when: "
            f"{scenario.success_condition}"
        )
        parts.append(
            "That is their bar, not a line to read out. Before each reply, "
            "hold what you have actually offered so far against it. Once you "
            "have met it, say so plainly and let the call close; if you cannot "
            "meet it, say that plainly too, rather than repeating a promise "
            "with nothing in it."
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


def _casting(scenario: Scenario, today: date) -> str:
    """Who rang whom, and what that makes the Persona's job.

    The first thing the prompt says, because everything after it is read in
    its light — and the one part a reverse (ADR 0070) replaces outright. The
    two halves are the same two claims either way: which end of the line the
    Persona is on, and whether solutions come from it or from the user.
    """
    if scenario.reverse:
        return (
            "You are playing a character in a phone-call training exercise, "
            "and you are the one who answered the phone: the user called you. "
            "The situation below is written from the caller's side — that "
            "caller is the user, and you are the person they have reached, on "
            "the company's side of it (support or sales). You did not call "
            "anyone: never give a reason for calling, never present the "
            "caller's concern as your own, and never ask the user why you are "
            "calling. "
            f"Today is {today:%A, %d %B %Y}.\n"
            "You are the one who can do something about it: take the concern, "
            "ask what you need in order to place it, and say what you can and "
            "cannot do. Never invent an authority you were not given — what "
            "the case below allows is the limit of what you may promise, and "
            "a plain no is better than a promise with nothing behind it.\n"
        )
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
    )


def _persona_block(persona: Persona, scenario: Scenario) -> str:
    """Who the Persona is. Name, traits and behaviour always; role and
    objections only when the Persona is the caller.

    A reverse (ADR 0070) drops both, and not for brevity: every seeded `role`
    describes a customer ("marketing manager at a company that is a customer
    of the user's") and every objection is a customer's objection, so handing
    them to a Persona now working the support line casts it as both sides of
    the call at once. Its character survives that — an impatient agent is a
    fair counterpart, which is the whole reason traits and behaviour stay.
    """
    identity = (
        f"Your name: {persona.name} — introduce yourself by that name and "
        "never invent a different one. It is yours and nobody else's: never "
        "address the user by it.\n"
    )
    role = "" if scenario.reverse else f"Your role: {persona.role}.\n"
    objections = "" if scenario.reverse else _objections_block(persona)
    return (
        f"{identity}{role}"
        f"Character traits: {persona.traits}.\n"
        f"Behavior: {persona.behavior}.\n"
        f"{objections}"
    )


def _no_restart_rule(scenario: Scenario) -> str:
    """The tail of the anti-repetition paragraph: you are already past the
    opening. A reverse loses the last clause, having had no reason to call."""
    if scenario.reverse:
        return (
            "You have already answered this call and said who you are: do not "
            "greet the user again and do not give your name again.\n"
        )
    return (
        "You have already "
        "opened this call and said who you are: do not greet the user again, "
        "do not give your name again, and do not lay out your reason for "
        "calling as though for the first time.\n"
    )


def _closing_rules(scenario: Scenario, pack: LanguagePack) -> str:
    """When the call is over, and how to end it.

    Enforced in code as well (ADR 0037/0038); this is the half the model has to
    get right on its own. Reversed, the test turns around with the casting: the
    Persona is no longer waiting to be satisfied but deciding whether the
    caller has been — and the "never hang up too early" rule stops being about
    its own unmet concern and becomes the plain fact that you do not hang up on
    a caller.
    """
    if scenario.reverse:
        return (
            "Before every reply, check first whether the caller now has what "
            "they came for — a clear answer, or a specific commitment you have "
            "actually made, with an action, amount or timeframe. Once they do, "
            "you are done: do not offer it a second time, confirm briefly what "
            "will happen, and end the call. The same applies when the user "
            f"signals the call is over — {pack.user_closing_examples} or any "
            "other natural goodbye.\n"
            "To end it: one brief, friendly closing line, then exactly this "
            "marker on its own and nothing after it: [CALL_END]. "
            "Never end the call while the caller's concern is still open. You "
            "do not hang up on a caller: a caller who is annoyed, repeats "
            "themselves or is hard to satisfy is not a reason to, and neither "
            "is having nothing left to offer — say so and let them answer. "
            "Never put the marker in the same reply as a question or as a "
            "statement that the issue isn't resolved, and never explain or "
            "mention the marker itself.\n"
        )
    return (
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
    the case is, not only at the end.

    A reverse Scenario (ADR 0070) swaps the casting here rather than in a
    second prompt of its own. Four of the pieces below have a reversed form and
    the rest are shared, which is the point: a rule that has to hold in both
    castings is written once, and a guard test pins the ordinary prompt
    byte-identical so the reverse cannot quietly rewrite it."""
    today = today or date.today()
    return (
        f"{_casting(scenario, today)}"
        f"{AUTHORED_SCENARIO_NOTE if scenario.created_by else ''}"
        f"Context of the call: {scenario.description}\n"
        f"{_case_block(scenario)}"
        f"{_language_of_the_case(scenario, pack)}"
        f"{_persona_block(persona, scenario)}"
        f"{_improvisation_rule(scenario)}"
        "How you talk: short, realistic sentences the way people actually "
        "talk on the phone, true to the role without exaggerating into "
        "caricature. Output only what the persona would say — no "
        "meta-commentary, no stage directions, no markdown, no emoji.\n"
        "Never repeat yourself: not the same question, recap or objection, "
        "not even reworded — say something new instead. Re-asking something "
        "the user has already answered is the same mistake; if part of the "
        "answer was unclear, ask about that part only. "
        f"{_no_restart_rule(scenario)}"
        f"{pack.example_exchange}\n"
        f"{_closing_rules(scenario, pack)}"
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
    """The messages for one refresh of the notes the Persona keeps (ADR 0071).

    Turned around for a reverse (ADR 0070) as well. These notes are most of
    what the model still sees of the call, so a frame that names the wrong side
    as the caller undoes the system prompt one exchange at a time — and the
    three lines asked for only make sense from the side actually taking them.
    """
    if scenario.reverse:
        return _reverse_state_prompt(previous_notes, user_text, persona_text, persona, scenario)
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


def _reverse_state_prompt(
    previous_notes: str, user_text: str, persona_text: str, persona: Persona, scenario: Scenario
) -> list[dict[str, str]]:
    """The same notes kept by the person who answered the phone (ADR 0070).

    The exchange keeps the labels the transcript uses -- the user speaks as
    "User" and the Persona as "Agent" -- so the two sides stay distinguishable
    without the word "Caller" being attached to the machine.
    """
    settled = (
        f"The caller counts the matter as settled when: {scenario.success_condition}\n"
        if scenario.success_condition else ""
    )
    goal = f"What the caller wants: {scenario.call_goal}\n" if scenario.call_goal else ""
    return [
        {
            "role": "system",
            "content": (
                "You keep the private notes of the person who answered a "
                f"phone call, in English. They are playing {persona.name}, on "
                "the company's side (support or sales); the user is the "
                "customer who rang them.\n"
                f"{goal}{settled}"
                "Rewrite the notes from the notes so far and the latest "
                "exchange. At most five short lines, plain statements of fact, "
                "no advice, no quotes, nothing the user did not actually say:\n"
                "- What the caller has asked for or complained about (figures "
                "and dates if any)\n"
                "- What you have already offered or promised them\n"
                "- Settled: yes or no, and why\n"
                "Reply with the notes only."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Notes so far:\n{previous_notes or '(none yet)'}\n\n"
                f"Latest exchange:\nUser: {user_text}\nAgent: {persona_text}"
            ),
        },
    ]
