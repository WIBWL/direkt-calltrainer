"""Verdicts on one reply against the call so far. Each answers one question and
acts on none; the order of consequences is the orchestrator's (ADR 0035, 0037, 0038)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from shared.language_packs import LanguagePack
from backend.session import repetition
from backend.session.nudges import strip_interrupted_mark


@dataclass(frozen=True)
class Ending:
    ends: bool
    # Logged together.
    marker: bool
    closing: bool
    repeated: bool
    restates: bool
    said_goodbye: bool
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
    """Whether a reply ends the call and whether a goodbye must follow (ADR 0102).
    On a repeat request, repeating the previous reply is the answer but an older
    one is still a loop. `said_goodbye` catches a model that withheld the marker
    on a reservation and signed off anyway."""
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
    previous = replies[-1] if replies else ""
    return bool(text.strip()) and previous.strip().lower() == text.strip().lower()


def repeats_earlier(text: str, replies: Sequence[str], *, exclude_last: bool = False) -> bool:
    """A verbatim repeat of an older reply (A-B-A-B). `exclude_last` when the user
    asked to hear the previous one again."""
    candidate = text.strip().lower()
    if len(candidate) < repetition.MIN_LOOP_REPLY_CHARS:
        return False
    earlier = replies[:-1] if exclude_last else replies
    return any(content.strip().lower() == candidate for content in earlier)


def restates_previous(text: str, replies: Sequence[str]) -> bool:
    return repetition.restates(text, replies[-1] if replies else "")


def reintroduces(first_chunk: str, replies: Sequence[str], pack: LanguagePack, first_name: str) -> bool:
    """A mid-call re-greeting at the start of the first chunk, so it can be
    regenerated instead of ending the call."""
    if not replies:
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
    """The first sentence if already said verbatim, so it is regenerated before
    synthesis; spoken, it could only end the call."""
    opening = repetition.first_sentence(first_chunk)
    if len(opening) < repetition.MIN_LOOP_REPLY_CHARS:
        return None
    candidate = opening.lower()
    for line in replies:
        if repetition.first_sentence(strip_interrupted_mark(line)).lower() == candidate:
            return opening
    return None


def said_sentences(replies: Sequence[str]) -> set[str]:
    return repetition.said_sentences(strip_interrupted_mark(line) for line in replies)


def still_pressing(text: str, pack: LanguagePack) -> bool:
    """Ends on a demand or question rather than a goodbye (ADR 0037). A farewell
    anywhere wins: half of legitimate endings trail a question after it."""
    if pack.farewell_re.search(text):
        return False
    last = repetition.last_sentence(text)
    return last.endswith("?") or bool(pack.still_pressing_re.search(last))
