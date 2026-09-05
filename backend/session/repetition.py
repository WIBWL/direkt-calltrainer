"""Text comparisons behind the repetition guards (ADR 0038).

Pure functions and the thresholds they are read against: no Session state, no
pipeline, nothing async. `SessionOrchestrator` supplies the history and decides
what a verdict means -- these only answer "how much of this text was already in
that one".

They live here rather than in `orchestrator.py` because they are self-contained
and that module had grown to its line ceiling, leaving no room to change the
guards without first making space.
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

# ADR 0038's verbatim check never fires on the failure below it: the Persona
# varies its opening sentence and carries the same block underneath it
# unchanged, Turn after Turn, so no two replies are ever wholly identical --
# the gap ADR 0038's own Consequences name. What separates a restatement from
# a caller legitimately quoting a figure twice is not *whether* a sentence
# came back but *how much* of the reply is old: a reply that repeats its
# opening and then says seven new things has moved the call on, one that is
# four fifths its predecessor has not. Measured against a real call, those two
# cases sit at 25% and 80%.
RESTATEMENT_SHARE = 0.5

# ...and a share needs more than one sentence to be a share *of*. With exactly
# one the test degenerates into "has this sentence been said before", which
# condemns a short confirmation — "Ganz genau. Der Betrag lag bei 480 Euro." is
# one long sentence, carried over, and ended the call. A reply that really has
# shrunk to one repeated sentence is caught on the next Turn by
# `_repeats_last_reply`, which is the cheap direction of the same trade.
MIN_RESTATEMENT_SENTENCES = 2


def first_sentence(text: str) -> str:
    """The first sentence of a chunk of text, for comparing openings."""
    return SENTENCE_SPLIT_RE.split(text.strip(), maxsplit=1)[0].strip()


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
    """True if most of `text` was already in `previous` — the partial form of a
    verbatim repeat (ADR 0038).

    A share of the reply, not a count of sentences: repeating one figure while
    adding new content is a real caller, repeating four fifths of the last reply
    is the loop the guard is for. Below `MIN_RESTATEMENT_SENTENCES` there is no
    share to take, so the reply is left alone.
    """
    sentences = set(long_sentences(text))
    if len(sentences) < MIN_RESTATEMENT_SENTENCES:
        return False
    carried = len(set(long_sentences(previous)) & sentences)
    return carried / len(sentences) > RESTATEMENT_SHARE
