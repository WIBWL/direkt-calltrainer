"""Text comparisons behind the repetition guards (ADR 0038): pure functions and
their thresholds; the orchestrator decides what a verdict means."""
from __future__ import annotations

import re

# Also splits "Nr. 4711"; the halves mostly fall under MIN_SENTENCE_LEN, so this
# costs precision, not correctness.
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
WORD_RE = re.compile(r"\w+", re.UNICODE)

# A first sentence sharing this much with the opening is the model re-reading it.
REINTRO_OVERLAP = 0.6

# Fewer words is an acknowledgement ("Ja, genau."), not an introduction.
MIN_REINTRO_WORDS = 3

# Shorter whole-reply repeats are natural acknowledgements.
MIN_LOOP_REPLY_CHARS = 30

# Shorter shared sentences are filler, not content.
MIN_SENTENCE_LEN = 15

# Old share of a reply: measured on a real call, 25 % moved on vs 80 % restated.
RESTATEMENT_SHARE = 0.5

# One sentence is no share; repeats_last catches it next Turn.
MIN_RESTATEMENT_SENTENCES = 2


# Three of the user's words in order is reading their line back; two ("Ja, gut")
# is a natural pick-up.
MIN_ECHO_WORDS = 3


def strip_echoed_prefix(text: str, echo: str) -> str:
    """`text` without a leading verbatim repeat of `echo`, word-wise."""
    echoed = WORD_RE.findall(echo.lower())
    if len(echoed) < MIN_ECHO_WORDS:
        return text
    end = 0
    for i, match in enumerate(WORD_RE.finditer(text)):
        if i == len(echoed):
            break
        if match.group().lower() != echoed[i]:
            return text
        end = match.end()
    else:
        if end == 0:
            return text
    return text[end:].lstrip(" \t,.;:!?-—…\"'")


def first_sentence(text: str) -> str:
    return SENTENCE_SPLIT_RE.split(text.strip(), maxsplit=1)[0].strip()


def last_sentence(text: str) -> str:
    return SENTENCE_SPLIT_RE.split(text.strip())[-1].strip()


def without_first_sentence(text: str) -> str:
    """The tail of a reply that opened mid-sentence, continuing the cut-off line."""
    parts = SENTENCE_SPLIT_RE.split(text.strip(), maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


# A resumed cut-off sentence starts the same and is often reworded later, so only
# its first words are compared.
MIN_RESUME_WORDS = 3
RESUME_PREFIX_WORDS = 5


def resumes(sentence: str, cut_off: str) -> bool:
    fragment = WORD_RE.findall(cut_off.lower())
    if len(fragment) < MIN_RESUME_WORDS:
        return False
    k = min(RESUME_PREFIX_WORDS, len(fragment))
    return WORD_RE.findall(sentence.lower())[:k] == fragment[:k]


def drop_resumed_sentences(text: str, cut_off: str) -> tuple[str, list[str]]:
    """Drops sentences resuming the cut-off one (ADR 0035); returns kept and dropped."""
    kept: list[str] = []
    dropped: list[str] = []
    for sentence in SENTENCE_SPLIT_RE.split(text.strip()):
        clean = sentence.strip()
        if clean and resumes(clean, cut_off):
            dropped.append(clean)
        elif clean:
            kept.append(clean)
    return " ".join(kept), dropped


def said_sentences(lines) -> set[str]:
    """Content sentences said so far; short lines recur naturally."""
    said: set[str] = set()
    for line in lines:
        said.update(s for s in long_sentences(line) if len(s) >= MIN_LOOP_REPLY_CHARS)
    return said


def drop_said_sentences(text: str, said: set[str]) -> tuple[str, list[str]]:
    """Drops sentences already said, so new ones pass without ending the call (ADR 0038)."""
    kept: list[str] = []
    dropped: list[str] = []
    for sentence in SENTENCE_SPLIT_RE.split(text.strip()):
        clean = sentence.strip()
        if len(clean) >= MIN_LOOP_REPLY_CHARS and clean.lower() in said:
            dropped.append(clean)
        elif clean:
            kept.append(clean)
    return " ".join(kept), dropped


def word_set(text: str) -> set[str]:
    return set(WORD_RE.findall(text.lower()))


def word_overlap(a: str, b: str) -> float:
    wa, wb = word_set(a), word_set(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def long_sentences(text: str) -> list[str]:
    sentences = (sentence.strip().lower() for sentence in SENTENCE_SPLIT_RE.split(text))
    return [sentence for sentence in sentences if len(sentence) >= MIN_SENTENCE_LEN]


def has_repeated_sentence(text: str) -> bool:
    sentences = long_sentences(text)
    return len(sentences) != len(set(sentences))


def restates(text: str, previous: str) -> bool:
    """A share, not a count: one repeated figure amid new content is a real caller."""
    sentences = set(long_sentences(text))
    if len(sentences) < MIN_RESTATEMENT_SENTENCES:
        return False
    carried = len(set(long_sentences(previous)) & sentences)
    return carried / len(sentences) > RESTATEMENT_SHARE
