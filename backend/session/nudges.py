"""The transient per-Turn instructions `SessionOrchestrator` slips in front of
the model, and the one mark it leaves in the history.

A nudge is appended to the message list for exactly one completion and never
stored (ADR 0037, ADR 0038, ADR 0035): each one names a situation the standing
system prompt is too far up-context to handle in a 4B model, and quotes the
concrete text the model should steer away from or pick up from. They live
here rather than in `orchestrator.py` because that module is at its line
ceiling, and because they are prose, not control flow -- read and revised
together, against transcripts.
"""

import re

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


# Carried on every turn past the opening (ADR 0038). presence_penalty does not
# stop a 4B model re-emitting a whole reply when the call stalls, and the
# system prompt's standing "never repeat yourself" is too far up-context to
# bite -- quoting the actual previous reply right before the model answers is
# what measurably moves it. The same asymmetry applies to the role: the
# standing rule sits in the system prompt and fades, while this nudge is what
# demands something new every turn -- and the newest material in context is
# whatever the user has just put on the table, so the cheapest way to comply is
# to hand that back as the persona's own contribution. Observed: the persona
# adopts the user's proposal, endorses it, then re-presents it as its own
# solution. Only the concrete move is named here; the standing "you are not the
# one who solves this" belongs in the system prompt, where it is paid once.
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

# Appended to the standing nudge above, so that the criterion the call ends on
# is the last thing in context before the model answers. It already stands in
# the system prompt, but the same recency problem applies to it as to the
# anti-repeat rule -- and worse: `ANTI_REPEAT_NUDGE` offers three moves, all of
# which carry the call on (press, give ground, ask something new), so the
# instruction sitting nearest the reply argued against closing. Played over every
# seeded Scenario against every Persona (`scripts/play_scenarios.py`), no pairing
# ever ended the call on the Turn its condition was met; the persona re-asked
# what had just been answered instead.
#
# The wording is the measured one, not the obvious one (ADR 0073). Written as an
# instruction -- "finish your reply with exactly this marker: [CALL_END]" -- it
# read as an order rather than a condition, and the persona appended the marker
# to its own opening question: 32 of 34 pairings hung up by probe 3. So the
# marker itself is not named here (the protocol stays in the system prompt, this
# only points at it), the open case is the branch stated first, and closing is
# gated on being able to quote back what met the criterion.
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

# What the check weighs the call against when the Scenario carries no success
# condition -- a user-authored one (ADR 0024), or one predating ADR 0045. Vaguer
# by necessity; the position in context is what does the work either way.
GENERIC_CRITERION = "what you came for has been given"

# Replies the persona has to have given -- its opening plus two answers --
# before the settlement check is attached at all. See
# `SessionOrchestrator._settlement_check`.
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

# Sent when a reply was caught opening with a sentence the Persona has already
# said earlier in the call, word for word, and is being regenerated (ADR 0038).
# Seen after two barge-ins in a row: the short cut-off lines left in the
# history are easy to reproduce, and the model reproduced one over an offer
# the user had just made. Caught on the first chunk, before it is spoken, so
# the call gets one fresh attempt instead of the loop guard's goodbye.
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

# Sent when a reply was nothing but the user's own line read back, and is
# being regenerated (ADR 0038). Seen live at the end of a negotiation: "36
# Stunden, das geht nicht früher." came back verbatim, twice, and the echo
# guard's stripping left an empty reply that the retry path then scored as an
# LLM failure -- a hard error on the trainee's screen for a model that had
# merely run out of things to say. One nudged retry first; if that is empty
# too, the call ends with the fixed sign-off, as any exhausted loop does.
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

# Appended to the history entry of a reply the user talked over (ADR 0035).
# The history keeps only the words that were heard, and a bare fragment read
# as a finished line is what disoriented the model: it tried to complete the
# sentence, or -- after an interrupted opening -- introduced itself all over
# again. A trailing dash is how written dialogue marks a cut-off line, which
# every model has seen far more often than any bracketed stage direction. It
# can still be *copied*: a reply that reproduced a dashed line from the
# history came back dash and all ("Ich will—"), so `strip_interrupted_mark`
# takes it back off every chunk before synthesis. Not part of
# `Turn.persona_text`: the Transcript gets its own, human-readable marker.
INTERRUPTED_MARK = "—"


def strip_interrupted_mark(text: str) -> str:
    """`text` without any copy of the cut-off mark -- inside a chunk it is a
    pause the model imitated from its own history, and at the end it would be
    read back into the Transcript as a line cut off that was not."""
    if INTERRUPTED_MARK not in text:
        return text
    return _MARK_RUN_RE.sub(" ", text).strip()


_MARK_RUN_RE = re.compile(rf"\s*{INTERRUPTED_MARK}+\s*")

# The turn right after that interruption (ADR 0035). Replaces the anti-repeat
# nudge, whose "your previous reply was: <fragment>" made the fragment look
# like a complete thought the model had to be different from -- and in that
# confusion it flailed.
#
# Unlike the other nudges this one goes *before* the user's message, not after
# it, and quotes nothing. A 4B model continues from whatever text sits last in
# its context: a first version that ended with the fragment quoted had the
# model finish that very sentence, word for word, over an offer the user had
# just made; the version before it, ending in "react to what they just said",
# had it read the user's line back out loud. With the nudge in between, the
# dashed line above it is what was cut off and the user's message below it is
# the last thing the model sees -- the one thing it should answer.
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
