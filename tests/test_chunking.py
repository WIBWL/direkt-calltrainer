"""TTS chunking of the streamed LLM output.

Covers ADR 0033: token stream -> sentence/clause-sized chunks so synthesis
(and playback) can start before the full reply is generated.
"""

from backend.session.chunking import (
    _FIRST_CHUNK_MIN_CHARS,
    _MAX_CHUNK_CHARS,
    _MIN_CHUNK_CHARS,
    sentence_chunks,
)

# pylint: disable=missing-function-docstring


async def _tokens(*parts):
    for p in parts:
        yield p


async def _chunks(*parts):
    return [c async for c in sentence_chunks(_tokens(*parts))]


async def test_short_reply_is_emitted_as_a_single_trailing_chunk():
    chunks = await _chunks("Ja", ", ", "gerne", ".")
    assert chunks == ["Ja, gerne."]


async def test_splits_on_sentence_end_once_past_the_minimum_length():
    first = "Das ist ein bewusst etwas laenger gehaltener erster Satz, der die Mindestlaenge klar ueberschreitet."
    assert len(first) >= _MIN_CHUNK_CHARS
    chunks = await _chunks(first + " ", "Und hier kommt noch ein zweiter Satz hinterher.")
    assert chunks[0] == first
    assert "zweiter Satz" in chunks[-1]


async def test_does_not_split_a_short_sentence_below_the_minimum():
    chunks = await _chunks("Kurz. ", "Auch kurz. ", "Und noch was.")
    # None of the intermediate sentence ends triggers a flush (buffer stays
    # under the minimum), so it all arrives as one final chunk.
    assert chunks == ["Kurz. Auch kurz. Und noch was."]


async def test_first_chunk_flushes_early_at_the_first_sentence(  # ADR 0033: first chunk sets perceived latency
):
    # First sentence is 40 chars — below _MIN_CHUNK_CHARS (80) but above the
    # first-chunk floor — so it is flushed immediately instead of waiting for
    # the second sentence.
    first = "Guten Tag, hier ist Herr Brandt am Apparat."
    assert _FIRST_CHUNK_MIN_CHARS <= len(first) < _MIN_CHUNK_CHARS
    chunks = await _chunks(first + " ", "Ich habe eine kurze Frage an Sie.")
    assert chunks[0] == first
    # the *second* chunk then needs the full minimum again, so this short
    # follow-on sentence only arrives as the trailing remainder
    assert chunks[1] == "Ich habe eine kurze Frage an Sie."


async def test_first_chunk_floor_still_rules_out_a_bare_greeting():
    # "Guten Tag." (10 chars) is below the first-chunk floor -> no early flush
    chunks = await _chunks("Guten Tag. ", "Was kann ich fuer Sie tun, bitte schoen?")
    assert chunks == ["Guten Tag. Was kann ich fuer Sie tun, bitte schoen?"]


async def test_long_unpunctuated_run_is_force_split_at_a_word_boundary():
    # 80 separate tokens, no sentence-ending punctuation anywhere.
    tokens = ["wort "] * 80
    chunks = [c async for c in sentence_chunks(_tokens(*tokens))]
    assert len(chunks) >= 2
    assert all(len(c) <= _MAX_CHUNK_CHARS for c in chunks[:-1])
    # split at a space -> no word is cut in half, no leading/trailing spaces
    assert all(c == c.strip() for c in chunks)
    assert " ".join(chunks).split() == "".join(tokens).split()


async def test_empty_stream_yields_nothing():
    assert await _chunks() == []
    assert await _chunks("", "   ", "") == []
