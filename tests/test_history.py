"""The call's record as the model has been told it (`backend/session/history.py`).

Covers ADR 0035 (trim/drop to what was heard), ADR 0038 (repetition guards read
earlier replies) and ADR 0071 (system prompt plus latest messages). The named
operations are pinned without a pipeline, a model or an event loop."""
from backend.session.history import History

# pylint: disable=missing-function-docstring


def _call() -> History:
    history = History("system prompt")
    history.add_reply("Guten Tag, Müller hier.")
    history.add_question("Worum geht es?")
    history.add_reply("Um den Export.")
    return history


def test_the_record_starts_with_the_system_prompt():
    history = History("system prompt")

    assert history.messages == [{"role": "system", "content": "system prompt"}]
    assert history.previous_reply() == ""
    assert history.replies() == []


def test_replies_are_read_oldest_first_and_the_last_is_the_previous():
    history = _call()

    assert history.replies() == ["Guten Tag, Müller hier.", "Um den Export."]
    assert history.previous_reply() == "Um den Export."


def test_a_reply_trimmed_to_what_was_heard_replaces_the_whole_one():
    history = _call()
    history.revise_reply("Um den—")

    assert history.messages[-1] == {"role": "assistant", "content": "Um den—"}
    assert "Um den Export." not in history.replies()


def test_a_reply_nobody_heard_leaves_the_question_open_to_extend():
    history = _call()
    history.drop_reply()
    history.extend_question("Worum geht es? Ich meine den Export.")

    assert history.messages[-1] == {"role": "user", "content": "Worum geht es? Ich meine den Export."}
    assert history.previous_reply() == "Guten Tag, Müller hier."


def test_a_late_revision_recognises_a_reply_it_no_longer_owns():
    history = _call()

    assert history.last_reply_is("Um den Export.")
    history.add_question("Und weiter?")
    assert not history.last_reply_is("Um den Export.")


def test_the_window_is_the_latest_messages_behind_the_system_prompt():
    history = _call()

    assert history.system() == {"role": "system", "content": "system prompt"}
    assert [m["content"] for m in history.recent(2)] == ["Worum geht es?", "Um den Export."]


def test_a_reader_cannot_rewrite_the_record():
    history = _call()
    history.messages[-1]["content"] = "rewritten"
    history.messages.append({"role": "user", "content": "smuggled"})

    assert history.previous_reply() == "Um den Export."
    assert len(history.messages) == 4
