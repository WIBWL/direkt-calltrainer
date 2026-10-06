"""The reply as TTS should read it: German stops in "1.400" and "6. Juli" read as
sentence ends, so they are removed. The transcript keeps the digits."""

import re

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

# Words that put a date in dative/accusative ("am sechsten Juli"). Usually right
# is enough: a wrong ending is a blemish, a stray stop is a break.
_INFLECTING = {
    "am", "vom", "zum", "beim", "seit", "bis", "ab", "nach", "vor", "den", "dem", "im", "des",
}

# Exactly three digits after the stop: a thousands separator.
_THOUSANDS_RE = re.compile(r"(?<=\d)\.(?=\d{3}(?!\d))")

_ORDINAL_MONTH_RE = re.compile(rf"(\b\w+\s+)?(\d{{1,2}})\.(\s+(?:{_MONTHS})\b)")

# "am 6." without a month. `der` is ambiguous and takes the plain form.
_ORDINAL_BARE_RE = re.compile(
    r"\b(am|im|vom|zum|beim|seit|bis|ab|den|dem|der|des)(\s+)(\d{1,2})\.(?!\s*\d)",
    re.IGNORECASE,
)


def _ordinal(day: int, inflected: bool) -> str | None:
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
    word = _ordinal(int(day), preposition.lower() in _INFLECTING)
    return match.group(0) if word is None else f"{preposition}{space}{word}"


def _german(text: str) -> str:
    text = _THOUSANDS_RE.sub("", text)
    text = _ORDINAL_MONTH_RE.sub(_ordinal_before_month, text)
    return _ORDINAL_BARE_RE.sub(_ordinal_after_preposition, text)


# English needs nothing undone.
_RULES = {"de": _german}


def for_speech(text: str, language_id: str) -> str:
    rule = _RULES.get(language_id)
    return rule(text) if rule else text
