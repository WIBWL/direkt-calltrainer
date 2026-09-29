"""The shape of a live-path request: one system message, and it is the first.

Covers:
  ADR 0103  every request the turn loop sends carries exactly one system
        message, at its head; the per-Turn nudges are folded into the user
        turn beside them, in the place they held, instead of travelling as
        system messages of their own -- which Gemini's OpenAI-compatible
        endpoint answered by dropping the system prompt, Persona and case
        with it.
  ADR 0035/0038  the place survives the folding: the interruption nudge still
        stands before the user's words, every other nudge after them.
"""

from backend.session.nudges import TURN_NOTE_FRAME, wire_messages
from backend.session.orchestrator import SessionOrchestrator
from tests.conftest import collect

# pylint: disable=missing-function-docstring


def _note(text):
    return TURN_NOTE_FRAME.format(note=text)


def test_a_request_without_notes_goes_out_unchanged():
    messages = [
        {"role": "system", "content": "prompt"},
        {"role": "user", "content": "Hallo."},
        {"role": "assistant", "content": "Guten Tag."},
    ]

    assert wire_messages(messages) == messages


def test_a_trailing_note_closes_the_last_user_message():
    wired = wire_messages([
        {"role": "system", "content": "prompt"},
        {"role": "user", "content": "Hallo."},
        {"role": "system", "content": "Say something new."},
    ])

    assert wired == [
        {"role": "system", "content": "prompt"},
        {"role": "user", "content": f"Hallo.\n\n{_note('Say something new.')}"},
    ]


def test_two_trailing_notes_keep_their_order():
    """The regeneration nudge is appended behind the standing one."""
    wired = wire_messages([
        {"role": "system", "content": "prompt"},
        {"role": "user", "content": "Hallo."},
        {"role": "system", "content": "first"},
        {"role": "system", "content": "second"},
    ])

    assert wired[-1]["content"] == f"Hallo.\n\n{_note('first')}\n\n{_note('second')}"


def test_a_note_before_the_users_words_opens_their_message():
    """ADR 0035: the interruption nudge stands between the cut-off line and the
    user's words, so that their words are what the model reads last."""
    wired = wire_messages([
        {"role": "system", "content": "prompt"},
        {"role": "assistant", "content": "Ich wollte gerade --"},
        {"role": "system", "content": "You were cut off."},
        {"role": "user", "content": "Moment, bitte."},
    ])

    assert wired[-1] == {"role": "user", "content": f"{_note('You were cut off.')}\n\nMoment, bitte."}
    assert wired[-1]["content"].endswith("Moment, bitte.")


def test_system_messages_ahead_of_the_conversation_join_the_system_prompt():
    """ADR 0071: the call notes sit right behind the system prompt."""
    wired = wire_messages([
        {"role": "system", "content": "prompt"},
        {"role": "system", "content": "notes"},
        {"role": "user", "content": "Hallo."},
    ])

    assert wired == [
        {"role": "system", "content": "prompt\n\nnotes"},
        {"role": "user", "content": "Hallo."},
    ]


def test_a_note_after_a_reply_becomes_a_user_turn_of_its_own():
    wired = wire_messages([
        {"role": "system", "content": "prompt"},
        {"role": "assistant", "content": "Hallo?"},
        {"role": "system", "content": "note"},
    ])

    assert wired[-1] == {"role": "user", "content": _note("note")}


def test_the_history_it_reads_is_left_alone():
    """The list handed in is the live history's own; folding a note into it
    would store the nudge, which ADR 0038 says is never stored."""
    user = {"role": "user", "content": "Hallo."}
    messages = [{"role": "system", "content": "prompt"}, user, {"role": "system", "content": "note"}]

    wire_messages(messages)

    assert user == {"role": "user", "content": "Hallo."}
    assert len(messages) == 3


async def test_every_request_of_a_call_carries_one_system_message_at_its_head(
    persona, scenario, fake_pipeline
):
    """The invariant over the real turn loop, not over the helper: whichever
    nudge a Turn gets, what reaches the LLM client has one system message."""
    orch = SessionOrchestrator(persona, scenario)
    fake_pipeline.stt.transcripts = [
        "Beispiel GmbH, Müller am Apparat, guten Tag.",
        "Worum geht es denn genau?",
        "Das schaue ich mir an.",
    ]
    fake_pipeline.llm.replies = [
        "Guten Tag, hier ist Thomas Brandt. Es geht um meinen Vertrag.",
        "Die Rechnung ist seit März zu hoch.",
        "Ich brauche bis Freitag eine Zahl.",
    ]

    for _ in range(3):
        await collect(orch.run_turn(b"webm-bytes", "turn.webm", "audio/webm"))

    assert len(fake_pipeline.llm.calls) >= 3
    for sent in fake_pipeline.llm.calls:
        roles = [m["role"] for m in sent]
        assert roles[0] == "system"
        assert "system" not in roles[1:], roles
