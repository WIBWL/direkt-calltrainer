"""Verdicts on one reply against the replies already given in this call.

Each check answers one question about a reply the model has just produced --
does it repeat, restate, restart the call, or end on a demand -- and none of
them does anything about the answer. What a verdict leads to (dropping a
sentence, regenerating, vetoing an end marker, ending the call) and in which
order the checks run is the orchestrator's, because that order *is* the
behaviour (ADR 0035, ADR 0037, ADR 0038).

They sat on `SessionOrchestrator` as methods whose only state was the history
they read, so testing one meant driving a whole Turn through a faked pipeline.
They take the replies as a list here, oldest first -- `History.replies()` --
and `repetition.py` stays the layer below: how much of one text is in another,
without knowing what a reply or a call is.
"""

from __future__ import annotations

from collections.abc import Sequence

from backend.session import repetition
from backend.session.language_packs import LanguagePack
from backend.session.nudges import strip_interrupted_mark


def repeats_last(text: str, replies: Sequence[str]) -> bool:
    """True if this reply repeats its predecessor verbatim (modulo case and
    whitespace) -- the cross-Turn form of `repetition.has_repeated_sentence`."""
    previous = replies[-1] if replies else ""
    return bool(text.strip()) and previous.strip().lower() == text.strip().lower()


def repeats_earlier(text: str, replies: Sequence[str], *, exclude_last: bool = False) -> bool:
    """True if this reply reproduces one the persona gave further back than the
    previous Turn, verbatim modulo case and whitespace -- an A-B-A-B
    oscillation, which `repeats_last` walks straight past because the repeat is
    two Turns back.

    A trivially short reply ("Ja, genau.") can recur across the call without
    being a loop, so only substantial ones count here -- unlike `repeats_last`,
    where an exact back-to-back repeat is degenerate at any length.

    `exclude_last` drops the immediately previous reply from the search: when
    the user asked to hear it again, reproducing *that* one is the answer, but
    reproducing one from further back is still a loop.
    """
    candidate = text.strip().lower()
    if len(candidate) < repetition.MIN_LOOP_REPLY_CHARS:
        return False
    earlier = replies[:-1] if exclude_last else replies
    return any(content.strip().lower() == candidate for content in earlier)


def restates_previous(text: str, replies: Sequence[str]) -> bool:
    """True if most of this reply was already in its predecessor -- the partial
    form of `repeats_last`."""
    return repetition.restates(text, replies[-1] if replies else "")


def reintroduces(first_chunk: str, replies: Sequence[str], pack: LanguagePack, first_name: str) -> bool:
    """Whether a reply *opens* by greeting or re-introducing after the call is
    already under way -- the model restarting the call instead of continuing
    it. Judged on the first chunk, before it is spoken, so the reply can be
    regenerated rather than the call ended.

    Narrow on purpose: a greeting at the very start of the reply, plus either
    the persona's own first name or the opening's wording carried over. A late
    "Guten Tag" mirrored back at a user who greeted first is the one legitimate
    case, and it still costs only a regeneration."""
    if not replies:  # the opening Turn -- greeting is correct here
        return False
    opener = first_chunk.strip()
    words = repetition.word_set(opener)
    if len(words) < repetition.MIN_REINTRO_WORDS:
        return False
    if not pack.regreeting_re.match(opener):
        return False
    if first_name and first_name in words:
        return True
    return repetition.word_overlap(opener, replies[0]) >= repetition.REINTRO_OVERLAP


def repeats_earlier_opening(first_chunk: str, replies: Sequence[str]) -> str | None:
    """The first sentence of `first_chunk` if the persona has already said
    exactly that sentence earlier in the call, else None. The pre-synthesis
    form of `repeats_earlier` / `repeats_last`: after two barge-ins the history
    holds short cut-off lines that a 4B model reproduces readily, and an exact
    repeat spoken out loud can only be answered by ending the call, so it is
    caught before synthesis and regenerated once instead. Short openers
    ("Ja, genau.") recur naturally and don't count."""
    opening = repetition.first_sentence(first_chunk)
    if len(opening) < repetition.MIN_LOOP_REPLY_CHARS:
        return None
    candidate = opening.lower()
    for line in replies:
        if repetition.first_sentence(strip_interrupted_mark(line)).lower() == candidate:
            return opening
    return None


def said_sentences(replies: Sequence[str]) -> set[str]:
    """Every content sentence the persona has said so far, normalised."""
    return repetition.said_sentences(strip_interrupted_mark(line) for line in replies)


def still_pressing(text: str, pack: LanguagePack) -> bool:
    """Whether a reply ends on a demand or a question rather than a goodbye
    (ADR 0037). A farewell anywhere in the reply wins outright: half of the
    legitimate endings measured in docs/research/model-parameters.md finish on
    a trailing question ("Auf Wiederhören. Darf ich mich melden?"), so the
    farewell decides, not the last sentence's shape."""
    if pack.farewell_re.search(text):
        return False
    last = repetition.last_sentence(text)
    return last.endswith("?") or bool(pack.still_pressing_re.search(last))
