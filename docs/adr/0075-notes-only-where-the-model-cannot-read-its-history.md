# ADR 0075: The Caller's Notes Are Kept Only Where the Model Cannot Read Its Own History

## Status

Accepted (narrows ADR 0071 to the gateway backend)

## Context

ADR 0071 decided that the dialogue model does not read the conversation. It reads the system prompt, a five-line summary of the call so far, and the last `HISTORY_WINDOW` (six) messages verbatim. That was the right decision for the backend it was written against: `Qwen3-4B-AWQ` misread the raw transcript past a handful of exchanges, turned its own case facts into questions to the user, and asked them for eight Turns.

ADR 0074 put a second backend behind the same code path, and named these notes as the first workaround to re-examine. Two properties of the summarisation make that worth doing rather than leaving alone.

**It is a fixed-size memory for a growing conversation.** `STATE_MAX_TOKENS` is 160 and the prompt asks for at most five lines — the same budget at exchange four and at exchange twenty-five. The compression ratio therefore worsens monotonically over a call, and what a support or sales call is actually about is the first thing that does not fit: three commitments with figures and dates, plus what is still open, plus settled yes/no, in five lines.

**It is rewritten from itself.** `build_state_prompt` is handed the previous notes and the latest exchange — never the history. A distortion introduced at exchange five has no source left to be corrected against on exchange six, and the notes reach the model framed as established fact (`STATE_NOTES_FRAME`). Errors do not merely accumulate; they are laundered.

Neither property is a defect. They are the cost of a compression that bought something real on a 4B model. On a model that reads its own transcript, nothing is bought and both costs are still paid — plus one background LLM request per exchange, which is half of what a Turn spends against a per-minute quota.

## Decision

The notes are kept where the model needs them and not otherwise. `CALL_STATE_NOTES` in `orchestrator.py` is `not GEMINI`: on the DiReKT gateway everything ADR 0071 describes is unchanged, byte-for-byte; on Gemini `_messages_for_turn` sends the system prompt, the whole of `self._messages`, and the Turn's nudge, and `_schedule_state_refresh` is a no-op so the summarisation request is never made.

The full history is sent unbounded. A Session is one phone call, so the record cannot outgrow a context measured in six figures, and a cap would be a limit invented for a case that does not arise.

This is deliberately derived from the backend rather than exposed as its own setting. Which shape is correct is a property of the model, not a preference, and the two are not independently choosable in any configuration that has been measured. An earlier iteration of this work did expose it as `CALL_STATE_NOTES` in `.env`; it was removed, because a switch invites the untested combination and the value it would carry is already implied by `GEMINI`.

`tests/conftest.py` claims `GEMINI` by assignment for the same reason it claims `POSTGRES_*`: this constant decides behaviour, and a developer's own `.env` — or a run inside the app container, where compose puts `.env` into the environment before pytest starts — must not silently decide which half of the code the suite exercises.

## Consequences

On Gemini a Turn costs one LLM request instead of two, and the model sees the opening exchange verbatim on Turn twenty instead of through a summary rewritten nineteen times. The drift described above cannot occur there, because there is no summary to drift.

Nothing else moves. `self._messages` was already the full record and the repetition guards, the barge-in trims (ADR 0035) and the Transcript already worked on it, so no guard changes behaviour; the settlement check reads the Scenario's success condition rather than the notes, so it does not either. `build_state_prompt`, `STATE_MAX_TOKENS` and `STATE_NOTES_FRAME` stay exactly as they are — they are live code on the default backend, not dead weight.

The cost is that two shapes now exist behind one code path, and only one of them is the default. `test_call_state.py` covers both: the ADR 0071 shape as the file's subject, and the shape here in two tests that patch the constant, one asserting the opening exchange survives verbatim and one asserting no summarisation request is made at all.
