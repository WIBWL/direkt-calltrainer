"""[CALL_END] marker handling and foreign-script scrubbing.

Covers ADR 0033 (streamed pipeline): the persona ends a call by emitting a
[CALL_END] marker in its text stream. The marker must never be spoken or
stored, and stray non-Latin script from the small model must be dropped
before synthesis.
"""

import pytest

from backend.session.orchestrator import (
    _ReplyProgress,
    _strip_end_marker,
    _strip_foreign_script,
)

# pylint: disable=missing-function-docstring


@pytest.mark.parametrize(
    "raw",
    ["Danke, auf Wiederhören. [CALL_END]", "Bis bald.[CALL_END]", "Tschüss. [call_end]", "Ende [ CALL END ]"],
)
def test_marker_is_detected_and_removed(raw):
    progress = _ReplyProgress()
    cleaned = _strip_end_marker(raw, progress)
    assert progress.ends_call is True
    assert "call" not in cleaned.lower()
    assert "[" not in cleaned


def test_text_without_marker_is_untouched():
    progress = _ReplyProgress()
    text = "Und wie sieht es mit der Laufzeit aus?"
    assert _strip_end_marker(text, progress) == text
    assert progress.ends_call is False


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Guten Tag 你好 zusammen", "Guten Tag  zusammen"),
        ("Alles klar。", "Alles klar"),
        ("こんにちは", ""),
        ("Nur deutscher Text.", "Nur deutscher Text."),
    ],
)
def test_foreign_script_is_scrubbed(raw, expected):
    assert _strip_foreign_script(raw) == expected
