"""Verdicts on one reply against the call so far (`backend/session/reply_checks.py`).

Covers ADR 0037 (still pressing is no goodbye; a farewell anywhere wins) and ADR 0038 (repeats,
A-B-A-B, restatements, re-greetings, a first sentence already said). Called directly, so a
threshold can be read against its own cases; the Turn-level tests live elsewhere."""
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


# --- The end-of-reply verdict (ADR 0037, ADR 0038) ---------------------------
# One verdict for "does this reply end the call" and "must a goodbye be said
# after it". They were two expressions in the orchestrator that had to agree,
# and the two recorded ways they failed to are the first two cases below.

def _ending(text, replies=(), *, marker=False, closing=False, allow_repetition=False):
    return checks.ending(
        text, list(replies), marker=marker, closing=closing,
        allow_repetition=allow_repetition, pack=DE,
    )


def test_a_closing_turn_with_no_words_still_says_goodbye():
    """The call used to end in silence: the closing path exempted itself from
    the fallback on the ground that the reply is the goodbye."""
    verdict = _ending("", closing=True)
    assert verdict.ends and verdict.needs_fallback


def test_a_goodbye_the_reply_said_itself_is_not_said_twice():
    verdict = _ending("Das kläre ich intern. Auf Wiederhören.")
    assert verdict.ends and verdict.said_goodbye
    assert not verdict.needs_fallback


def test_a_nudged_closing_is_its_own_goodbye():
    verdict = _ending("Vielen Dank, dann bis bald.", closing=True)
    assert verdict.ends and not verdict.needs_fallback


def test_an_unprompted_marker_ends_the_call_with_a_goodbye_added():
    verdict = _ending("Gut, dann ist das geklärt.", marker=True)
    assert verdict.ends and verdict.needs_fallback


def test_a_repeated_reply_ends_the_call_unless_a_repeat_was_asked_for():
    assert _ending(LONG, [LONG]).repeated
    verdict = _ending(LONG, [LONG], allow_repetition=True)
    assert not verdict.ends


def test_an_ordinary_reply_does_not_end_the_call():
    verdict = _ending("Wann passt Ihnen ein Termin?", [OPENING])
    assert not verdict.ends and not verdict.needs_fallback
