"""`SpokenReply.cut`: what was heard of a streamed reply (ADR 0035)."""

# pylint: disable=missing-function-docstring

from backend.session.heard import BARGE_IN_GRACE_MS, SpokenReply


def _reply(*chunks: tuple[str, int]) -> SpokenReply:
    """A reply whose chunks were each voiced and fully synthesized."""
    reply = SpokenReply()
    for text, ms in chunks:
        reply.voice(text)
        reply.add_audio(ms)
        reply.finish_chunk(text)
    return reply


def test_a_chunk_played_to_its_end_is_heard_whole():
    reply = _reply(("Guten Tag.", 1000), ("Wie kann ich helfen?", 1500))
    cut = reply.cut(1000 - BARGE_IN_GRACE_MS)
    assert cut.heard == "Guten Tag."
    assert cut.unheard == "Wie kann ich helfen?"


def test_the_chunk_cut_into_is_heard_up_to_a_whole_word():
    reply = _reply(("Guten Tag.", 1000), ("Wie kann ich Ihnen heute helfen?", 2000))
    cut = reply.cut(1000 + 1000 - BARGE_IN_GRACE_MS)
    assert cut.heard.startswith("Guten Tag. Wie")
    assert not cut.heard.endswith(" ")
    assert cut.heard + " " + cut.unheard == "Guten Tag. Wie kann ich Ihnen heute helfen?"


def test_the_opening_sentence_still_being_synthesized_counts():
    reply = SpokenReply()
    reply.voice("Guten Tag, hier ist die Stadtwerke-Hotline.")
    reply.add_audio(2000)
    cut = reply.cut(1200)
    assert cut.heard, "the first words the user got are kept"
    assert cut.heard.startswith("Guten")


def test_nothing_played_is_nothing_heard():
    reply = _reply(("Guten Tag.", 1000))
    cut = reply.cut(0 - BARGE_IN_GRACE_MS)
    assert cut.heard == ""
    assert cut.unheard == "Guten Tag."


def test_no_played_position_counts_everything_dispatched():
    reply = _reply(("Guten Tag.", 1000), ("Wie kann ich helfen?", 1500))
    cut = reply.cut(None)
    assert cut.heard == "Guten Tag. Wie kann ich helfen?"
    assert cut.unheard == ""


def test_the_grace_is_the_benefit_of_the_doubt_on_the_next_sentence():
    reply = _reply(("Guten Tag.", 1000), ("Wie kann ich helfen?", 1500))
    assert reply.cut(1000).heard == "Guten Tag. Wie"
