"""Per-Turn instructions, each used for one completion and never stored: the
system prompt is too far up-context for a small model (ADR 0035, 0037, 0038)."""

import re
from dataclasses import dataclass

# Marked as established fact, so the model does not re-ask what the notes record (ADR 0071).
STATE_NOTES_FRAME = (
    "Where the call stands so far (your own notes -- these are established "
    "facts, do not ask about them again):\n"
)

CLOSING_NUDGE = (
    "The user just signaled the call is over. End it now: add one brief, "
    "friendly closing line, then finish your reply with exactly this "
    "marker and nothing after it: [CALL_END]."
)


# Every turn past the opening (ADR 0038): quoting the previous reply right before
# the answer measurably works. The last lines stop the Persona adopting the
# user's offer as its own.
ANTI_REPEAT_NUDGE = (
    'Your previous reply in this call was:\n"{previous}"\n'
    "Say something genuinely different now: react to what the user just said, "
    "press a point you have not pressed yet, give ground, or ask a new "
    "question about your own concern — in new words. Do not repeat or reword "
    "that reply, and do not greet or introduce yourself again.\n"
    "If the user has just put something on the table, respond to it — take "
    "it, press it for the specifics it is still missing, or say why it falls "
    "short — but never put that same offer forward yourself as though it "
    "were your own idea."
)

# For a `hard` Persona: measured, the ordinary nudge's "give ground" outweighed a
# character set far up the prompt. That clause is dropped, not forbidden.
ANTI_REPEAT_NUDGE_HARD = (
    'Your previous reply in this call was:\n"{previous}"\n'
    "Say something genuinely different now: react to what the user just said, "
    "press a point you have not pressed yet, name what it costs you that this "
    "is still open, or say what you will do instead — in new words. Do not "
    "repeat or reword that reply, and do not greet or introduce yourself "
    "again.\n"
    "If the user has just put something on the table, respond to it — take "
    "it, press it for the specifics it is still missing, or say why it falls "
    "short — but never put that same offer forward yourself as though it "
    "were your own idea."
)

# Reverse (ADR 0070): putting an offer forward is now the Persona's job.
ANTI_REPEAT_NUDGE_REVERSE = (
    'Your previous reply in this call was:\n"{previous}"\n'
    "Say something genuinely different now: react to what the caller just "
    "said, answer the part of it you have not answered yet, put forward what "
    "you can actually do, or ask for the one detail you still need — in new "
    "words. Do not repeat or reword that reply, and do not greet or introduce "
    "yourself again.\n"
    "If the caller has just told you something, use it: place it against what "
    "your records say, and either act on it or say plainly why you cannot. Do "
    "not hand their own request back to them as a question."
)

# Last in context, so the ending criterion is (ADR 0073). Naming [CALL_END] here
# made the Persona hang up on its opening question, so the marker is not named.
SETTLEMENT_CHECK = (
    "\nOne question to settle before you send that reply. What ends this call is: "
    "{criterion}. Has the user actually given you that, in words you could quote "
    "back to them? Count what arrived piece by piece, and what you had to ask "
    "twice to get. If any part of it is still open, or you are about to ask a "
    "question of your own, then it has not been given: answer as described above "
    "and carry the call on. Only if you could quote it back has it been given, "
    "and then stop pressing -- accept it in your own words, thank them, and close "
    "the call the way your instructions describe."
)

# Reversed, the question is whether the Persona has given it; asked the other way,
# the model pressed the caller for what the caller rang about.
SETTLEMENT_CHECK_REVERSE = (
    "\nOne question to settle before you send that reply. What ends this call is: "
    "{criterion}. Have you actually given the caller that, in words they could "
    "quote back to you? Count what you offered piece by piece over several "
    "replies. If any part of it is still open, or you are about to ask a "
    "question of your own, then it has not been given: answer as described "
    "above and carry the call on. If you cannot give it at all, say so plainly "
    "-- that is an answer too, and the call can close on it. Only once it has "
    "actually been given do you stop: confirm briefly what will happen and "
    "close the call the way your instructions describe."
)

# When the Scenario has no criterion.
GENERIC_CRITERION = "what you came for has been given"
GENERIC_CRITERION_REVERSE = "the caller has what they rang about"

# Opening plus two answers before the check is attached.
SETTLEMENT_CHECK_AFTER_REPLIES = 3

# Re-asking a reply that re-greeted (ADR 0038), quoting the rejected opening.
REGENERATE_NUDGE = (
    'You just started your reply with:\n"{opening}"\n'
    "That restarts the call — you have already greeted the user and said who "
    "you are. Answer again without any greeting or self-introduction: pick up "
    "the conversation where it stands and respond to the user's last message."
)

# Re-asking a reply that opened with an already-said sentence (ADR 0038).
REPEAT_OPENING_NUDGE = (
    'You just started your reply with:\n"{opening}"\n'
    "You have already said exactly that earlier in this call, and the user "
    "heard it. Do not say it again, in any wording. Respond to the user's "
    "last message with something new: answer what they asked, take a position "
    "on what they offered, or ask them about it."
)

# The user asked to hear it again: the same content, shorter, never verbatim.
CLARIFY_NUDGE = (
    "The user did not catch your previous reply. Say the same thing again, but "
    "reworded: shorter, plainer words, one or two sentences. Do not read your "
    "previous reply back word for word, and do not greet or introduce yourself."
)

# Asked again: a third rendering will not help.
CLARIFY_AGAIN_NUDGE = (
    "The user still did not follow, even after you rephrased. Do not put it a "
    "third time. Ask which part is unclear, or give the single most important "
    "point in one sentence and carry the call forward."
)

# Re-asking a reply that was only the user's words read back (ADR 0038).
ECHO_NUDGE = (
    'You just repeated the user\'s own words back to them:\n"{opening}"\n'
    "That is not an answer. Respond to what they said in your own words: "
    "accept it, say what is still missing, or ask about it -- and do not "
    "repeat their sentence."
)

# Re-asking a reply that only resumed the cut-off sentence (ADR 0035).
RESUME_NUDGE = (
    'You just picked the sentence the user cut off back up:\n"{opening}"\n'
    "They cut you off there on purpose, and finishing it is not an answer. Do "
    "not say that sentence again in any wording. Respond to what the user "
    "said instead, in your own words."
)

# Ends a cut-off line in the history (ADR 0035). The model copies it, so it is
# stripped from every chunk before synthesis.
INTERRUPTED_MARK = "—"


def strip_interrupted_mark(text: str) -> str:
    if INTERRUPTED_MARK not in text:
        return text
    return _MARK_RUN_RE.sub(" ", text).strip()


_MARK_RUN_RE = re.compile(rf"\s*{INTERRUPTED_MARK}+\s*")

# After a barge-in (ADR 0035). Placed before the user's message and quotes
# nothing: the model continues from whatever sits last in its context.
INTERRUPTED_NUDGE = (
    "Your last line above ends with a dash: the user cut you off there, "
    "mid-sentence, and nothing after the dash was said. What follows is what "
    "they said over you. Answer that directly, in your own words, and answer "
    "it first: do not pick the cut-off thought back up before you have "
    "responded -- if it still matters afterwards, make it in one sentence, "
    "otherwise let it go. Do not repeat the cut-off sentence, do not lay your "
    "concern out again -- they have heard it -- and do not greet or introduce "
    "yourself again. If they have just offered, promised or proposed "
    "something, take a position on that before anything else."
)


@dataclass(frozen=True)
class TurnNudge:
    content: str
    # Placed before the last user message, so that message is what the model sees last.
    before_last: bool = False


def settlement_check(replies: int, *, reverse: bool, call_goal: str) -> str:
    """Empty over the opening exchanges, where most premature hang-ups landed (ADR 0073)."""
    if replies < SETTLEMENT_CHECK_AFTER_REPLIES:
        return ""
    if reverse:
        return SETTLEMENT_CHECK_REVERSE.format(
            criterion=call_goal.strip() or GENERIC_CRITERION_REVERSE
        )
    return SETTLEMENT_CHECK.format(criterion=call_goal.strip() or GENERIC_CRITERION)


def for_turn(  # pylint: disable=too-many-arguments  # each is one situation the precedence weighs
    *,
    closing: bool,
    interrupted: bool,
    repeat_requests: int,
    previous_reply: str,
    replies: int,
    reverse: bool,
    hard: bool,
    call_goal: str,
) -> TurnNudge | None:
    """Closing > interrupted > repeat request (firmer the second time) > the
    anti-repeat reminder with the settlement check. A reverse's form wins over
    `hard`."""
    if closing:
        return TurnNudge(CLOSING_NUDGE)
    if interrupted:
        return TurnNudge(INTERRUPTED_NUDGE, before_last=True)
    if repeat_requests >= 2:
        return TurnNudge(CLARIFY_AGAIN_NUDGE)
    if repeat_requests == 1:
        return TurnNudge(CLARIFY_NUDGE)
    if previous_reply:
        if reverse:
            frame = ANTI_REPEAT_NUDGE_REVERSE
        elif hard:
            frame = ANTI_REPEAT_NUDGE_HARD
        else:
            frame = ANTI_REPEAT_NUDGE
        return TurnNudge(
            frame.format(previous=previous_reply) +
            settlement_check(replies, reverse=reverse, call_goal=call_goal)
        )
    return None
