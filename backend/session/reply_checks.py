"""Verdicts on one reply against the replies already given in this call.

Each check answers one question and acts on none: what a verdict leads to, and
in which order, is the orchestrator's, since that order *is* the behaviour
(ADR 0035, ADR 0037, ADR 0038). `repetition.py` is the text layer below."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from backend.session import repetition
from backend.session.language_packs import LanguagePack
from backend.session.nudges import strip_interrupted_mark


@dataclass(frozen=True)
class Ending:
    """Whether a finished reply ends the call, and why."""

    ends: bool
    # Why, each reason on its own: they are logged together.
    marker: bool
    closing: bool
    repeated: bool
    restates: bool
    said_goodbye: bool
    # A fallback goodbye has to be spoken after the reply.
    needs_fallback: bool


def ending(  # pylint: disable=too-many-arguments  # the reasons a call ends, each its own input
    text: str,
    replies: Sequence[str],
    *,
    marker: bool,
    closing: bool,
    allow_repetition: bool,
    pack: LanguagePack,
) -> Ending:
    """Whether a finished reply ends the call, and whether a goodbye must follow.

    `marker` is the model's [CALL_END], already past ADR 0037's veto; `closing`
    backstops it on a Turn the user closed. On a repeat request, repeating the
    *previous* reply is the answer, but an older one is still a loop (ADR 0038).
    `said_goodbye` catches the obedient model: it withholds the marker on a reply
    voicing a reservation, then signs off anyway, which left the call hanging.
    The fallback goodbye is needed where nobody asked for one (repeat, unprompted
    marker), never where the reply said its own, and always on a wordless reply."""
    spoke = bool(text)
    repeated = spoke and (
        repetition.has_repeated_sentence(text) or
        repeats_earlier(text, replies, exclude_last=allow_repetition) or
        (not allow_repetition and repeats_last(text, replies))
    )
    restates = spoke and not allow_repetition and restates_previous(text, replies)
    said_goodbye = spoke and not marker and bool(pack.farewell_re.search(text))
    ends = marker or closing or repeated or restates or said_goodbye
    return Ending(
        ends=ends,
        marker=marker,
        closing=closing,
        repeated=repeated,
        restates=restates,
        said_goodbye=said_goodbye,
        needs_fallback=ends and (
            not spoke or repeated or restates or (marker and not closing)
        ),
    )


def repeats_last(text: str, replies: Sequence[str]) -> bool:
    """True if this reply repeats its predecessor verbatim (modulo case and
    whitespace) -- the cross-Turn form of `repetition.has_repeated_sentence`."""
    previous = replies[-1] if replies else ""
    return bool(text.strip()) and previous.strip().lower() == text.strip().lower()


def repeats_earlier(text: str, replies: Sequence[str], *, exclude_last: bool = False) -> bool:
    """True if this reply reproduces, verbatim modulo case, one given further back
    than the previous Turn (an A-B-A-B oscillation `repeats_last` misses). Short
    replies don't count. `exclude_last` skips the previous reply when the user
    asked to hear it again."""
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
    """Whether a reply *opens* by greeting or re-introducing mid-call, judged on
    the first chunk so it can be regenerated rather than the call ended. Narrow:
    a greeting at the very start plus the persona's first name or the opening's
    wording; a mirrored late "Guten Tag" costs only a regeneration."""
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
    """The first sentence of `first_chunk` if the persona already said exactly
    that earlier in the call, else None. Pre-synthesis form of `repeats_earlier`:
    a 4B model readily reproduces short cut-off lines, and a spoken repeat can only
    end the call, so it is regenerated once instead. Short openers don't count."""
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
