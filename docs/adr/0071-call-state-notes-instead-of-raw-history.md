# ADR 0071: The Model Reads Its Notes and the Last Exchanges, Not the Whole History

## Status

Accepted (narrowed by ADR 0075 — this describes the gateway backend; where the
dialogue model reads its own history, the notes and the window are not used)

## Context

The dialogue model is locked to `Qwen3-4B-AWQ` (`docs/research/model-parameters.md`: the larger models on the gateway return 403 since the trial phase ended). Over a day of live calls the same shape kept coming back: the first two or three exchanges are fine, then the persona loses the thread. In one session it turned its own case fact — *a callback was promised* — into a question to the user ("Haben Sie den Callback versprochen?"), asked it for eight Turns, and attributed its own facts to the user ("Sie haben gesagt, dass es nicht passiert ist"). A 9-character Whisper hallucination (`*Titelm*`) became a real Turn in the middle of it and made things worse.

What the model was holding at that point: a system prompt of ~1.5k tokens of English rules (forty-odd, grown one incident at a time under ADR 0037/0038/0045), the complete, unbounded history, and a per-Turn nudge. Sampling was already at the model card's recommendation. Every guard added on top of this (ADR 0035 and ADR 0038's amendments, all on 2026-09-06) fixed one symptom and two of them caused their own; that road is exhausted. What a 4B model demonstrably cannot do is keep ten Turns of noisy transcript straight *and* follow forty rules. What it can do is answer the last exchange well when told, in a few lines, where the call stands.

## Decision

Three changes, all on what the model is *given*, none on the model.

**1. A short, sectioned system prompt.** `backend/session/prompting.py` keeps every decision the earlier prompt encoded (the calling role, ADR 0043's language rule, ADR 0045's case/goal/condition and objections, the ADR 0037/0038 ending protocol, F-12's no-stage-directions) and drops the rest of the wording. One line is new, because its absence is what the log showed: the case facts are *things you know and the user does not — never ask the user about them, never attribute them to the user*. The anti-repetition and ending machinery the model kept ignoring is enforced in code and only named here.

**2. The caller's notes replace the history beyond the last exchanges.** `SessionOrchestrator._messages` remains the complete record — the repetition guards, the barge-in trims (ADR 0035) and the Transcript all work on it. But what is sent to the model (`_messages_for_turn`) is now: the system prompt; a system message carrying *the caller's notes* on the call so far, framed as established fact; the last `HISTORY_WINDOW` (six: three exchanges) messages verbatim; and the Turn's nudge. The notes are produced by the same model, non-thinking, from the previous notes and the exchange that just completed, against a structured prompt of three labelled lines — what the user has said, offered or promised; what the caller still wants; settled yes/no and why (`build_state_prompt`). That refresh runs **in the background** after a reply is committed, never on the path to the next reply (latency is the project's first priority, ADR 0033/0044), and it runs again when a barge-in trims the reply, so the notes never record words the user did not hear. A failed refresh keeps the previous notes: stale beats none, and the call must not depend on this leg. The Session cancels a refresh still in flight when it ends.

**3. Phantom transcripts are not Turns.** Whisper does not return an empty transcript on near-silence; it invents a phrase in the audio's language, or a non-speech annotation. A transcript that is *nothing but* one of these — a per-language `stt_phantom_re` in the language pack plus a language-independent annotation pattern — gets no reply and no history entry; the Turn opened for it is taken back and the Session returns to listening. Whole-message patterns only, and "Danke." stays a real answer: the primary defence is still the client's VAD threshold, this is the second.

## Consequences

The model's view of a call stops growing: it is the system prompt, a few lines of notes and three exchanges, whatever the call's length — which is the property the raw history lacked, and the reason a long call got *worse*. The user's commitments survive as notes even once the exchange they were made in has left the window, so "in zwei Tagen" said at minute two is still a fact at minute five. The cost is one extra, short LLM completion per exchange, off the critical path, and a one-exchange lag in the notes when the model is slow — the window covers that exchange verbatim anyway.

The risks are the ones any summary carries: the notes can be wrong, and a wrong note is now stated as fact to the model. The structured prompt, the *nothing the user did not actually say* rule and the refresh-on-trim keep that narrow, and the notes are one system message the log can show. The prompt shortening kept every pinned decision (the ~30 assertions in `tests/test_system_prompt.py` still pass), so what changed is wording and structure, not behaviour on paper — its effect on the live model is measured the way the parameter research was, against real calls, not by these tests. If a larger model becomes available again, this design costs nothing and stays right; it is simply less necessary.
