"""Stops after digits are removed for TTS only (ADR 0033, 0044)."""

import pytest

from backend.clients.speech_text import for_speech

# pylint: disable=missing-function-docstring


@pytest.mark.parametrize(
    "written,spoken",
    [
        ("Das sind 1.400 Euro im Monat.", "Das sind 1400 Euro im Monat."),
        ("Wir reden über 12.500 Euro.", "Wir reden über 12500 Euro."),
    ],
)
def test_thousands_separator_is_dropped(written, spoken):
    assert for_speech(written, "de") == spoken


@pytest.mark.parametrize(
    "written,spoken",
    [
        ("Der Termin ist am 6. Juli.", "Der Termin ist am sechsten Juli."),
        ("Der 6. Juli passt mir.", "Der sechste Juli passt mir."),
        ("Bis zum 21. Dezember.", "Bis zum einundzwanzigsten Dezember."),
    ],
)
def test_ordinal_before_a_month_becomes_a_word(written, spoken):
    assert for_speech(written, "de") == spoken


@pytest.mark.parametrize(
    "written,spoken",
    [
        ("Wir sprechen uns am 14.", "Wir sprechen uns am vierzehnten"),
        ("Das läuft seit dem 3.", "Das läuft seit dem dritten"),
        # Not a day of the month, but the same full stop and the same fix.
        ("Im 2. Quartal entscheiden wir.", "Im zweiten Quartal entscheiden wir."),
    ],
)
def test_bare_ordinal_after_a_preposition_becomes_a_word(written, spoken):
    assert for_speech(written, "de") == spoken


@pytest.mark.parametrize(
    "written,spoken",
    [
        # The three shapes the recorded runs actually produced.
        ("Der 14. ist also der Fix?", "Der vierzehnte ist also der Fix?"),
        ("Ich will wissen, ob der 12. noch frei ist.",
         "Ich will wissen, ob der zwölfte noch frei ist."),
        ("Ist der 14. der einzige Tag?", "Ist der vierzehnte der einzige Tag?"),
        # Genitive takes the -n, and "des" is decidable where "der" is not.
        ("Der Stand des 6. ist offen.", "Der Stand des sechsten ist offen."),
    ],
)
def test_ordinal_in_subject_position_becomes_a_word(written, spoken):
    assert for_speech(written, "de") == spoken


def test_a_sentence_that_merely_ends_in_a_number_is_left_alone():
    text = "Damit sind es 30. Der Rest bleibt offen."
    assert for_speech(text, "de") == text


def test_a_day_out_of_range_is_left_as_written():
    text = "Die Ticketnummer ist 45. Bitte notieren."
    assert for_speech(text, "de") == text


def test_english_passes_through_untouched():
    text = "That is 1,400 euros as of July 6. Nothing else changed."
    assert for_speech(text, "en") == text
    assert for_speech(text, "fr") == text
