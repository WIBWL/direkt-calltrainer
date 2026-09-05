"""Rewrites a reply into the form a TTS backend should read aloud.

Applied at the boundary in `tts.py`, so it changes only what is spoken. The
Transcript keeps the digits, which is what a reader wants -- "1.400 Euro" and
"6. Juli" are correct German, they are just unspeakable as written.

German marks both a thousands separator and an ordinal with a full stop, and
both reach the pipeline looking exactly like the end of a sentence. That costs
twice over: `session/chunking.py` flushes a chunk at a sentence end, so the
reply is cut into two synthesis calls with an audible gap between them, and
within a chunk the TTS drops into a falling, end-of-sentence intonation.

Removing the character fixes both. The digits are deliberately *not* spelled
out as words: once the full stop is gone a bare "1400" is read correctly, and
a German number-to-words conversion would be a large amount of code whose
errors would be heard on every call. Ordinals are the exception -- "6 Juli" is
not German -- so those become words, and only those.

Unknown languages pass through untouched: a missing rule must never be able to
fail a synthesis.
"""

import re

# Ordinals only go as high as a day of the month, which is all the full stop
# after a number ever means here.
_ORDINAL_STEMS = {
    1: "erste", 2: "zweite", 3: "dritte", 4: "vierte", 5: "fünfte",
    6: "sechste", 7: "siebte", 8: "achte", 9: "neunte", 10: "zehnte",
    11: "elfte", 12: "zwölfte", 13: "dreizehnte", 14: "vierzehnte",
    15: "fünfzehnte", 16: "sechzehnte", 17: "siebzehnte", 18: "achtzehnte",
    19: "neunzehnte", 20: "zwanzigste", 21: "einundzwanzigste",
    22: "zweiundzwanzigste", 23: "dreiundzwanzigste", 24: "vierundzwanzigste",
    25: "fünfundzwanzigste", 26: "sechsundzwanzigste", 27: "siebenundzwanzigste",
    28: "achtundzwanzigste", 29: "neunundzwanzigste", 30: "dreißigste",
    31: "einunddreißigste",
}

_MONTHS = (
    "Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember"
)

# The words that put a date into the dative or accusative, where the ordinal
# takes an -n ("am sechsten Juli"). Anything else keeps the plain form ("der
# sechste Juli"). Getting the ending wrong is a blemish; leaving the full stop
# in is a break in the middle of a sentence, so this only has to be usually
# right.
_INFLECTING = {"am", "vom", "zum", "beim", "seit", "bis", "ab", "nach", "vor", "den", "dem", "im"}

# "1.400" -> "1400". Three digits after the stop and no fourth: a thousands
# separator, never a sentence that happens to end in a digit.
_THOUSANDS_RE = re.compile(r"(?<=\d)\.(?=\d{3}(?!\d))")

# "6. Juli", with whatever word came before it so the ending can be chosen.
_ORDINAL_MONTH_RE = re.compile(rf"(\b\w+\s+)?(\d{{1,2}})\.(\s+(?:{_MONTHS})\b)")

# "am 6." with no month behind it -- still an ordinal, still a full stop.
_ORDINAL_BARE_RE = re.compile(
    r"\b(am|vom|zum|beim|seit|bis|ab|den|dem)(\s+)(\d{1,2})\.(?!\s*\d)",
    re.IGNORECASE,
)


def _ordinal(day: int, inflected: bool) -> str | None:
    """The day as a spoken German ordinal, or None if it is not a day."""
    stem = _ORDINAL_STEMS.get(day)
    if stem is None:
        return None
    return stem + "n" if inflected else stem


def _ordinal_before_month(match: re.Match[str]) -> str:
    before, day, rest = match.group(1) or "", match.group(2), match.group(3)
    word = _ordinal(int(day), before.strip().lower() in _INFLECTING)
    return match.group(0) if word is None else f"{before}{word}{rest}"


def _ordinal_after_preposition(match: re.Match[str]) -> str:
    preposition, space, day = match.group(1), match.group(2), match.group(3)
    word = _ordinal(int(day), True)
    return match.group(0) if word is None else f"{preposition}{space}{word}"


def _german(text: str) -> str:
    text = _THOUSANDS_RE.sub("", text)
    text = _ORDINAL_MONTH_RE.sub(_ordinal_before_month, text)
    return _ORDINAL_BARE_RE.sub(_ordinal_after_preposition, text)


# English writes neither a thousands separator nor an ordinal with a full stop,
# so there is nothing here to undo.
_RULES = {"de": _german}


def for_speech(text: str, language_id: str) -> str:
    """The text as the TTS backend should receive it."""
    rule = _RULES.get(language_id)
    return rule(text) if rule else text
