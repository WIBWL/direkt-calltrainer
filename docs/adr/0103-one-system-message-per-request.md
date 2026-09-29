# ADR 0103: One System Message per Request; Per-Turn Instructions Travel in the User Turn

## Status

Accepted. Changes how the nudges of ADR 0035, ADR 0037, ADR 0038, ADR 0073 and ADR 0102 reach the model, not what they say or where they stand. Changes how the call notes of ADR 0071 reach it in the same way.

## Context

On 2026-09-26 a trainee answered the phone to Andreas Kastner in the Scenario "Kündigungsabsicht wegen Preis" and heard: "Guten Tag, Herr Kessler, mein Name ist Julia Brandt, ich rufe an wegen der offenen Posten aus dem letzten Quartal." The name was wrong, the concern was wrong, and neither came from anywhere in the application.

The cause was the shape of the request. The system prompt, which carries the Persona and the case, has always been the first message. Every per-Turn instruction the orchestrator adds (the anti-repeat nudge and settlement check, the closing push, the clarify nudges, the interruption nudge, the regeneration nudges, and since ADR 0102 the opening instruction) went in as a further message with the role `system`, placed at the end of the list or, for the interruption, just before the user's words. The placement is deliberate: what sits nearest the reply is what the model follows (ADR 0038).

Gemini's OpenAI-compatible endpoint, which ADR 0074 made the dialogue backend, keeps only one system message. Given a second, the first is gone, whichever position the second takes. Measured against `gemini-3.5-flash-lite` with a three-message request and none of this application's code:

| Request | Answer to "Wie heißen Sie und was ist Ihr Beruf?" |
|---|---|
| system prompt ("Du bist Andreas Kastner, Geschäftsführer …"), question | "Mein Name ist Andreas Kastner, und ich bin Geschäftsführer." |
| the same plus a second system message after the question | "Ich heiße ChatGPT und arbeite als KI-Sprachmodell …" |
| the same with the second system message before the question | "Ich bin eine KI ohne eigenen Namen …" |

Replaying the orchestrator's own requests gave the same result on the real prompt. As sent, the opening named an invented person in 2 of 2 attempts, and a mid-call question about the case was answered without a single case fact, once from the seller's side. With the trailing instruction removed, sent as `user`, or merged into the system prompt, the model had the right name and the right facts in every attempt.

Qwen3-4B on vLLM, the backend the nudges were written against, renders every system message in place through its chat template, so nothing was lost there. The defect arrived on 2026-09-08 with the Gemini option. From then on, every Turn after the opening ran on the conversation and the nudge alone. The opening itself survived, because `run_opening_turn` sent its instruction as a `user` message. The Persona therefore introduced itself correctly and the history carried the name forward, which is why the calls looked sound. ADR 0102 moved the opening into the nudged path, and with that the loss reached the first sentence, where it could be heard.

Two consequences reach beyond the one call. Every Gemini transcript from that period shows a Persona with neither character nor case after its opening line. The persona comparisons run with `scripts/play_scenarios.py` on 2026-09-24/25 measured the conversation and the nudge, not the Persona.

## Decision

We will send every live-path request in the one shape every chat API reads the same way: **a single system message at the head, followed only by user and assistant turns.**

Per-Turn instructions stay what and where they are. They are still built as system messages in `orchestrator._messages_for_turn` and in the regeneration path, and on the way out `nudges.wire_messages` folds each into the user turn beside it, in the place it held:

- An instruction at the end closes the last user message. This covers the anti-repeat nudge, the settlement check, the closing push, the clarify nudges, the regeneration nudges and the opening instruction.
- An instruction before the user's words opens their message. This covers the interruption nudge, whose position ADR 0035 chose so that the user's words are the last thing the model reads.
- System messages ahead of the conversation join the system prompt. These are the call notes of ADR 0071.

A folded instruction carries a frame (`TURN_NOTE_FRAME`) saying that it is a note from the exercise, not something the user said, and that it is followed and never mentioned. The frame stands at the note itself rather than as a rule in the system prompt, because it has to be read at the point of use.

The rule is applied once, at the single call into `llm.stream_reply` in the orchestrator, so no nudge added later can bypass it. It applies whatever the backend: a correction for Gemini alone would leave the next backend to find the same trap. The requests outside the live path (wrap-up, follow-up, reverse briefing, call notes refresh, PDF summary) already have this shape.

## Consequences

The Persona and the case reach the model on every Turn on Gemini. Replayed against the call that prompted this record, the opening named Andreas Kastner and the Insight-Analytics package, and the mid-call answer gave the role, the fourteen licences, the 1,180 euros and the twelve-percent increase from the case facts, in both attempts.

The nudges now carry the authority of a user turn rather than a system message. On Gemini this is strictly better, since before they carried the only authority and the system prompt none. On a backend that rendered them in place, such as the Qwen setup ADR 0038 was measured against, their effect may differ, and the measurements behind ADR 0038 and ADR 0073 were taken in the old shape. The DiReKT gateway no longer serves Qwen: on 2026-09-26 the key was limited to `whisper-large-v3-turbo` and `gemma-4-26B-A4B-it`, and Gemma could not be reached that day. The change is therefore verified on Gemini only, and has to be checked on Gemma before that backend is relied on.

`tests/test_wire_messages.py` pins the rule twice: on `wire_messages` alone, and over a real run of the turn loop, where no request that reaches the LLM client may carry a system message after the first. The tests that read the request to find a nudge now find it inside the user turn.

Transcripts and sweeps recorded under Gemini before this change are not evidence about a Persona. Measurements of how much a Persona shapes a call have to be taken again.
