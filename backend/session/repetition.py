"""Text comparisons behind the repetition guards (ADR 0038).

Pure functions and their thresholds: no Session state, nothing async. The
orchestrator supplies the history and decides what a verdict means.
"""
from __future__ import annotations

import re

# Splits after any of .!? — so a German abbreviation ("Rechnung Nr. 4711") is
# cut in two. Both halves usually fall under MIN_SENTENCE_LEN and drop out; what
# survives is a fragment, which only ever matches an identical fragment, so it
# costs precision rather than correctness.
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
WORD_RE = re.compile(r"\w+", re.UNICODE)

# First sentence of a reply shares at least this fraction of its words with the
# opening's — the model is reading its own introduction back out (ADR 0038).
REINTRO_OVERLAP = 0.6

# Below this many words a reply's opening is an acknowledgement ("Ja, genau."),
# not an introduction, whatever greeting token it happens to contain.
MIN_REINTRO_WORDS = 3

# Below this, a whole reply repeating an earlier one is more likely a natural
# short acknowledgement than the model looping (ADR 0038).
MIN_LOOP_REPLY_CHARS = 30

# Below this, a shared sentence means shared filler ("Ja, genau.", "Ich
# verstehe.") rather than shared content, so short ones are not compared.
MIN_SENTENCE_LEN = 15

# ADR 0038's verbatim check misses a Persona that varies its opening and carries
# the same block underneath. What separates that from quoting a figure twice is
# how much of the reply is old: measured on a real call, 25% vs 80%.
RESTATEMENT_SHARE = 0.5

# ...and a share needs more than one sentence: with one, a carried-over short
# confirmation ended the call. A reply shrunk to one repeated sentence is caught
# next Turn by `reply_checks.repeats_last`.
MIN_RESTATEMENT_SENTENCES = 2


# A reply that opens with this many of the user's own words, in order, is
# reading their line back before answering it -- seen on the Turn after a
# barge-in, where the nudge's "react to what they just said" was resolved by
# reciting it. Two words ("Ja, gut") are a natural pick-up; three in a row are
# not.
MIN_ECHO_WORDS = 3


def strip_echoed_prefix(text: str, echo: str) -> str:
    """`text` without a leading verbatim repeat of `echo` (word-wise, case and
    punctuation aside), or unchanged if it does not open with one. Cut at the
    end of the last echoed word, then the punctuation the echo carried along."""
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
    """The first sentence of a chunk of text, for comparing openings."""
    return SENTENCE_SPLIT_RE.split(text.strip(), maxsplit=1)[0].strip()


def last_sentence(text: str) -> str:
    """The last sentence of a reply, for judging how it ends."""
    return SENTENCE_SPLIT_RE.split(text.strip())[-1].strip()


def without_first_sentence(text: str) -> str:
    """`text` minus its first sentence -- the tail of a reply that opened
    mid-sentence, continuing the line the user had cut off (ADR 0035)."""
    parts = SENTENCE_SPLIT_RE.split(text.strip(), maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


# A sentence that opens with this many of the cut-off sentence's words, in
# order, is that sentence picked back up from the top -- finished this time,
# and usually reworded towards the end, which is why the whole sentence is
# never the thing compared. Under MIN_RESUME_WORDS the fragment ("Ich will")
# is too little to match on.
MIN_RESUME_WORDS = 3
RESUME_PREFIX_WORDS = 5


def resumes(sentence: str, cut_off: str) -> bool:
    """True if `sentence` starts the way the cut-off sentence did (ADR 0035)."""
    fragment = WORD_RE.findall(cut_off.lower())
    if len(fragment) < MIN_RESUME_WORDS:
        return False
    k = min(RESUME_PREFIX_WORDS, len(fragment))
    return WORD_RE.findall(sentence.lower())[:k] == fragment[:k]


def drop_resumed_sentences(text: str, cut_off: str) -> tuple[str, list[str]]:
    """`text` without the sentences that pick the cut-off sentence back up
    from the top, plus the ones dropped. The user cut that sentence off on
    purpose; the reply after a barge-in is for what they said, not for
    finishing it (ADR 0035)."""
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
    """Every sentence in `lines` long enough to count as content, normalised --
    what the persona has already said in this call, for `drop_said_sentences`.
    The floor is `MIN_LOOP_REPLY_CHARS`, the same one the cross-Turn verbatim
    check uses: a short line recurs naturally, a long one does not."""
    said: set[str] = set()
    for line in lines:
        said.update(s for s in long_sentences(line) if len(s) >= MIN_LOOP_REPLY_CHARS)
    return said


def drop_said_sentences(text: str, said: set[str]) -> tuple[str, list[str]]:
    """`text` without the sentences already in `said`, plus the ones dropped.
    The chunk-level restatement check, before a chunk is spoken: the model carries
    the same block under a varied opening (ADR 0038) and re-delivers a cut-off part,
    so dropping carried sentences lets the new ones through without ending the call."""
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
    """The distinct lower-cased words in `text`."""
    return set(WORD_RE.findall(text.lower()))


def word_overlap(a: str, b: str) -> float:
    """Jaccard overlap of the two texts' word sets — 0.0 when either is empty."""
    wa, wb = word_set(a), word_set(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def long_sentences(text: str) -> list[str]:
    """The sentences of one reply worth comparing: normalised, filler dropped."""
    sentences = (sentence.strip().lower() for sentence in SENTENCE_SPLIT_RE.split(text))
    return [sentence for sentence in sentences if len(sentence) >= MIN_SENTENCE_LEN]


def has_repeated_sentence(text: str) -> bool:
    """True if a non-trivial sentence repeats within one reply — the model
    looping (ADR 0038). Short fragments ("Ja.", "Okay.") don't count."""
    sentences = long_sentences(text)
    return len(sentences) != len(set(sentences))


def restates(text: str, previous: str) -> bool:
    """True if most of `text` was already in `previous`, the partial form of a
    verbatim repeat (ADR 0038). A share, not a count: repeating one figure amid new
    content is a real caller. Below `MIN_RESTATEMENT_SENTENCES` there is no share."""
    sentences = set(long_sentences(text))
    if len(sentences) < MIN_RESTATEMENT_SENTENCES:
        return False
    carried = len(set(long_sentences(previous)) & sentences)
    return carried / len(sentences) > RESTATEMENT_SHARE
