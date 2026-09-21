"""Verdicts on one reply against the call so far (`backend/session/reply_checks.py`).

Covers:
  ADR 0037  a reply that still presses is not a goodbye; a farewell anywhere wins
  ADR 0038  verbatim repeats, A-B-A-B oscillation, restatements, re-greetings
            and a first sentence already said are recognised

Each check used to be reachable only by driving a Turn through the faked
pipeline, which is how `test_repetition_guard.py` and `test_closing_intent.py`
still exercise them in place. These call them directly, so a threshold or a
pattern can be changed and read against its own cases.
"""
from backend.session import reply_checks as checks
from backend.session.language_packs import get_pack

# pylint: disable=missing-function-docstring

DE = get_pack("de")
OPENING = "Guten Tag, hier ist Thomas Berger von der Firma Hansen."
LONG = "Das Ticket ist seit elf Tagen offen und ich brauche einen Termin."


def test_a_verbatim_repeat_of_the_last_reply_is_caught_at_any_length():
    assert checks.repeats_last("Ja, genau.", ["Hallo.", "ja, genau. "])
    assert not checks.repeats_last("Ja, genau.", [])


def test_an_oscillation_two_replies_back_is_caught_when_it_is_substantial():
    replies = [LONG, "Wann kommt der Techniker?"]

    assert checks.repeats_earlier(LONG, replies)
    assert not checks.repeats_earlier("Ja, genau.", ["Ja, genau.", "Nein."]), "too short to be a loop"


def test_repeating_the_last_reply_on_request_is_not_a_loop():
    """The user asked to hear it again: the previous reply is the answer."""
    assert not checks.repeats_earlier(LONG, ["Hallo.", LONG], exclude_last=True)
    assert checks.repeats_earlier(LONG, [LONG, "Hallo."], exclude_last=True)


def test_a_restatement_is_read_against_the_previous_reply_only():
    second = "Ich möchte heute noch wissen, wann der Techniker vorbeikommt."
    reply = f"{LONG} {second}"

    assert checks.restates_previous(reply, ["Hallo.", reply])
    assert not checks.restates_previous(reply, [reply, "Hallo."]), "only the last one counts"
    assert not checks.restates_previous(reply, [])


def test_a_greeting_with_the_persona_s_own_name_restarts_the_call():
    replies = [OPENING, "Es geht um den Export."]

    assert checks.reintroduces("Guten Tag, hier ist Thomas noch einmal.", replies, DE, "thomas")


def test_a_greeting_is_right_on_the_opening_turn():
    assert not checks.reintroduces(OPENING, [], DE, "thomas")


def test_a_short_greeting_mirrored_back_is_let_through():
    assert not checks.reintroduces("Guten Tag.", [OPENING], DE, "thomas")


def test_an_opening_sentence_already_said_is_returned_for_the_nudge():
    replies = [OPENING, f"{LONG} Können Sie das prüfen?"]

    assert checks.repeats_earlier_opening(f"{LONG} Noch etwas.", replies) == LONG
    assert checks.repeats_earlier_opening("Ja, genau. Weiter.", ["Ja, genau."]) is None


def test_a_reply_ending_on_a_question_is_still_pressing():
    assert checks.still_pressing("Ich will wissen, wann der Export wieder geht?", DE)


def test_a_farewell_anywhere_wins_over_a_trailing_question():
    assert not checks.still_pressing("Auf Wiederhören. Darf ich mich melden?", DE)
