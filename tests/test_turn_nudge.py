"""Which nudge a reply gets (`backend/session/nudges.py::for_turn`).

Covers:
  ADR 0035  the cut-off push outranks everything but the goodbye, and goes in
            front of the user's message
  ADR 0037  the goodbye push outranks everything
  ADR 0038  the clarify pushes, then the standing anti-repeat reminder
  ADR 0070  the reverse turns the reminder around
  ADR 0073  the settlement check rides on the reminder alone, after the opening

The precedence used to be an if-cascade inside the orchestrator, reachable only
through `_messages_for_turn` (which `test_closing_intent.py` still drives); it
is a table here.
"""

from backend.session import nudges

# pylint: disable=missing-function-docstring

PREVIOUS = "Das Ticket ist seit elf Tagen offen."


def _for(**over):
    situation = {
        "closing": False, "interrupted": False, "repeat_requests": 0,
        "previous_reply": PREVIOUS, "replies": nudges.SETTLEMENT_CHECK_AFTER_REPLIES,
        "reverse": False, "call_goal": "einen Termin",
    }
    return nudges.for_turn(**(situation | over))


def test_the_goodbye_outranks_everything():
    nudge = _for(closing=True, interrupted=True, repeat_requests=2)
    assert nudge.content == nudges.CLOSING_NUDGE


def test_the_cut_off_push_comes_next_and_goes_before_the_users_message():
    nudge = _for(interrupted=True, repeat_requests=2)
    assert nudge.content == nudges.INTERRUPTED_NUDGE
    assert nudge.before_last


def test_a_second_request_to_repeat_is_firmer_than_the_first():
    assert _for(repeat_requests=1).content == nudges.CLARIFY_NUDGE
    assert _for(repeat_requests=2).content == nudges.CLARIFY_AGAIN_NUDGE


def test_the_standing_reminder_quotes_the_last_reply_and_carries_the_settlement_check():
    nudge = _for()
    assert PREVIOUS in nudge.content
    assert "einen Termin" in nudge.content
    assert not nudge.before_last


def test_the_settlement_check_is_withheld_over_the_opening():
    nudge = _for(replies=nudges.SETTLEMENT_CHECK_AFTER_REPLIES - 1)
    assert "einen Termin" not in nudge.content


def test_a_reverse_turns_the_reminder_around():
    assert _for(reverse=True).content.startswith(
        nudges.ANTI_REPEAT_NUDGE_REVERSE.format(previous=PREVIOUS)
    )


def test_nothing_to_steer_away_from_is_no_nudge():
    assert _for(previous_reply="") is None
