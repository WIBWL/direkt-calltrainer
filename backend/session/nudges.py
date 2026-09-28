"""The transient per-Turn instructions `SessionOrchestrator` slips in front of
the model, and the one mark it leaves in the history.

A nudge is used for exactly one completion and never stored (ADR 0035, ADR 0037,
ADR 0038): the system prompt is too far up-context for a 4B model. `for_turn` picks one."""

import re
from dataclasses import dataclass

# Frames the caller's notes in the model's view of the call (ADR 0071). They
# sit right after the system prompt, ahead of the last few exchanges, and are
# marked as established fact so the model does not re-ask what they record.
STATE_NOTES_FRAME = (
    "Where the call stands so far (your own notes -- these are established "
    "facts, do not ask about them again):\n"
)

CLOSING_NUDGE = (
    "The user just signaled the call is over. End it now: add one brief, "
    "friendly closing line, then finish your reply with exactly this "
    "marker and nothing after it: [CALL_END]."
)


# Carried on every turn past the opening (ADR 0038): presence_penalty and the
# system prompt's standing rule are too weak; quoting the previous reply right
# before the answer measurably works. The last lines stop the persona adopting
# the user's proposal as its own, the cheapest way to "say something new".
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

# The reverse form (ADR 0070): the ordinary one's last lines forbid putting an
# offer forward, which reversed is the persona's job and would contradict the
# casting from the position nearest the reply. Only the demand for something new stays.
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

# Appended to the standing nudge so the ending criterion is the last thing in
# context: with only `ANTI_REPEAT_NUDGE` (whose moves all carry the call on) no
# pairing ever ended on the Turn its condition was met. Worded as measured
# (ADR 0073): phrased as an instruction naming [CALL_END], the persona appended the
# marker to its opening question (32 of 34 pairings hung up by probe 3). So the
# marker is not named, the open case comes first, and closing needs a quotable answer.
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

# The same check for a reverse (ADR 0070), where the criterion is the caller's
# and the persona is the one who has to meet it. The direction is the whole
# difference: asked the question above while playing the support side, the
# model read "has the user given you that" as its own demand and started
# pressing the caller for the thing the caller had rung about.
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

# What the check weighs the call against when the Scenario carries no success
# condition -- a user-authored one (ADR 0024), or one predating ADR 0045. Vaguer
# by necessity; the position in context is what does the work either way.
GENERIC_CRITERION = "what you came for has been given"
GENERIC_CRITERION_REVERSE = "the caller has what they rang about"

# Replies the persona has to have given -- its opening plus two answers --
# before the settlement check is attached at all. See `settlement_check`
# below, which is where that decision moved.
SETTLEMENT_CHECK_AFTER_REPLIES = 3

# Sent when a reply was caught opening with a greeting again and is being
# regenerated (ADR 0038). The rejected opening is quoted so the retry has
# something concrete to steer away from.
REGENERATE_NUDGE = (
    'You just started your reply with:\n"{opening}"\n'
    "That restarts the call — you have already greeted the user and said who "
    "you are. Answer again without any greeting or self-introduction: pick up "
    "the conversation where it stands and respond to the user's last message."
)

# Sent when a reply opens with a sentence the Persona already said verbatim and is
# being regenerated (ADR 0038), e.g. a cut-off line reproduced after barge-ins.
# Caught on the first chunk, so the call gets a retry instead of the loop guard's goodbye.
REPEAT_OPENING_NUDGE = (
    'You just started your reply with:\n"{opening}"\n'
    "You have already said exactly that earlier in this call, and the user "
    "heard it. Do not say it again, in any wording. Respond to the user's "
    "last message with something new: answer what they asked, take a position "
    "on what they offered, or ask them about it."
)

# The user asked to hear the last reply again (ADR 0038). Given half a chance
# the 4B model reads its previous line back verbatim -- and a wall of text is
# no clearer the second time -- so the ask is for the same content, reworded
# shorter.
CLARIFY_NUDGE = (
    "The user did not catch your previous reply. Say the same thing again, but "
    "reworded: shorter, plainer words, one or two sentences. Do not read your "
    "previous reply back word for word, and do not greet or introduce yourself."
)

# They have asked more than once now. A third rendering of the same content,
# however worded, is not helping -- find out what is unclear or move on.
CLARIFY_AGAIN_NUDGE = (
    "The user still did not follow, even after you rephrased. Do not put it a "
    "third time. Ask which part is unclear, or give the single most important "
    "point in one sentence and carry the call forward."
)

# Sent when a reply was nothing but the user's own line read back and is being
# regenerated (ADR 0038); stripping the echo left an empty reply that surfaced as
# an LLM failure. If the retry is empty too, the call ends with the fixed sign-off.
ECHO_NUDGE = (
    'You just repeated the user\'s own words back to them:\n"{opening}"\n'
    "That is not an answer. Respond to what they said in your own words: "
    "accept it, say what is still missing, or ask about it -- and do not "
    "repeat their sentence."
)

# Sent when a reply after a barge-in was nothing but the cut-off sentence
# picked back up -- from the top, or its tail continued -- and is being
# regenerated (ADR 0035). The filters drop such sentences wherever they sit
# in a reply; this is for the reply that had nothing else in it.
RESUME_NUDGE = (
    'You just picked the sentence the user cut off back up:\n"{opening}"\n'
    "They cut you off there on purpose, and finishing it is not an answer. Do "
    "not say that sentence again in any wording. Respond to what the user "
    "said instead, in your own words."
)

# Appended to the history entry of a reply the user talked over (ADR 0035): a bare
# fragment read as a finished line made the model complete it or re-introduce
# itself. The model can copy it, so `strip_interrupted_mark` removes it from every
# chunk before synthesis. The Transcript gets its own human-readable marker.
INTERRUPTED_MARK = "—"


def strip_interrupted_mark(text: str) -> str:
    """`text` without any copy of the cut-off mark -- inside a chunk it is a
    pause the model imitated from its own history, and at the end it would be
    read back into the Transcript as a line cut off that was not."""
    if INTERRUPTED_MARK not in text:
        return text
    return _MARK_RUN_RE.sub(" ", text).strip()


_MARK_RUN_RE = re.compile(rf"\s*{INTERRUPTED_MARK}+\s*")

# The turn right after that interruption (ADR 0035), replacing the anti-repeat
# nudge. Unlike the others it goes *before* the user's message and quotes
# nothing: a 4B model continues from whatever sits last in its context. Ending on
# the quoted fragment made it finish that sentence; ending on "react to what they
# just said" made it read the user's line back. The user's message must be last.
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
    """This reply's nudge, and where it goes."""

    content: str
    # Between the history's last user message and the one before it, rather
    # than after the whole view: `INTERRUPTED_NUDGE` is placed so the user's
    # message is what the model sees last (see there).
    before_last: bool = False


def settlement_check(replies: int, *, reverse: bool, call_goal: str) -> str:
    """The reminder that the call may end now, phrased around the Scenario's
    call goal where it has one (ADR 0073); empty over the opening exchanges,
    where nine of ten premature hang-ups landed and no condition can yet be met.
    A reverse asks it from the other end of the line (ADR 0070).
    """
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
    call_goal: str,
) -> TurnNudge | None:
    """The one nudge this reply gets, or None, in order of precedence.

    Closing (ADR 0037) > interrupted (ADR 0035; only where the view ends on the
    user's message) > repeat request, firmer the second time (ADR 0038) > the
    anti-repeat reminder plus the settlement check, turned around for a reverse (ADR 0070)."""
    if closing:
        return TurnNudge(CLOSING_NUDGE)
    if interrupted:
        return TurnNudge(INTERRUPTED_NUDGE, before_last=True)
    if repeat_requests >= 2:
        return TurnNudge(CLARIFY_AGAIN_NUDGE)
    if repeat_requests == 1:
        return TurnNudge(CLARIFY_NUDGE)
    if previous_reply:
        frame = ANTI_REPEAT_NUDGE_REVERSE if reverse else ANTI_REPEAT_NUDGE
        return TurnNudge(
            frame.format(previous=previous_reply) +
            settlement_check(replies, reverse=reverse, call_goal=call_goal)
        )
    return None
