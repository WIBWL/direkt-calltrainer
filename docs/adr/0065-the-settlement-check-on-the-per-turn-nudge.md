# ADR 0065: The Settlement Check Rides on the Per-Turn Nudge

## Status

Accepted. Refines ADR 0037 (closing intent) and ADR 0038 (the per-turn nudges);
uses the `success_condition` that ADR 0045 put on the Scenario.

## Context

`scripts/play_scenarios.py` plays every seeded Scenario against every Persona
and records, per pairing, *after which probe* the persona closed the call
itself. Over 34 pairings the answer was the same everywhere:

| the persona closed | pairings |
|---|---|
| on the Turn its `success_condition` was met | 0 of 34 |
| only once the user said goodbye | 28 of 34 |
| never — the call ended on a backstop | 6 of 34 |

The system prompt asks for the first case in as many words ("Once it has been
given you are done … accept it out loud in your own words … and end the call"),
so this is not a Scenario finding. It says the closing protocol does no work at
the moment it is supposed to: a trainee who resolves the matter perfectly gets
the same call as one who does not, and only the user's own farewell — which
`_signals_closing` turns into `force_end_call` — ever ends anything. In
production that failure is invisible, because the backstop covers it.

### It is not the marker, and not a missing criterion

A model-emitted `[CALL_END]` is honoured: `_generate_reply` sets
`ends_call = progress.ends_call or force_end_call or …`. And the criterion does
reach the model — `_case_block` hands over the `success_condition` with a usage
rule attached (ADR 0045).

The transcripts show the failure happening earlier than either. In
`deadline-correction`, the probe satisfies the condition literally — a new date
*and* what happens to the appointment hanging off it — and the persona answers
by asking whether the third-party appointment still stands, which is the half of
the sentence it had just been given. It never got as far as needing a marker.

### What sat next to the reply argued against closing

Every Turn past the opening carries a transient system message
(`_messages_for_turn`, ADR 0038). Outside a closing or repeat-request turn that
message is `_ANTI_REPEAT_NUDGE`, and it offers exactly three moves: press a point
not yet pressed, give ground, or ask a new question — then, for whatever the user
has just put on the table: take it, press it for missing specifics, or say why it
falls short. Six options, all of which continue the call.

That message is the last thing in context before the model answers. The
permission to close sits some forty lines up in the system prompt, framed by a
prohibition that was longer, more concrete and carried examples from the language
pack. ADR 0038 already established that recency is what moves this model.

## Decision

**1. The criterion the call ends on is restated on every Turn past the opening.**
`_SETTLEMENT_CHECK` is appended to `_ANTI_REPEAT_NUDGE` in the same system
message. A Scenario with no `success_condition` — a user-authored one (ADR 0024),
or one predating ADR 0045 — falls back to `_GENERIC_CRITERION`.

**2. It is phrased as a question with the open case first, and does not name the
marker.** This is the part that had to be measured rather than reasoned out; see
below.

**3. It is withheld until the persona's third reply**
(`_SETTLEMENT_CHECK_AFTER_REPLIES`). On the opening exchanges the check has one
honest answer, and the model gave the other one.

**4. The prohibition in the system prompt is cut to about half its length.**
Every constraint it carried is kept — the vague reassurance with no specifics,
the frustrated reply, the empty promise, no marker in the same reply as a
question, never explain the marker. What goes is the repetition and the hedging
that made it outweigh the permission standing beside it.

**5. The harness gets a sixth probe.** `SETTLE` sits between the concrete answer
and the farewell: a neutral follow-up that concedes nothing and adds nothing.
Without it, a persona that needs one beat to register what it was handed is
indistinguishable from one that never registers it, because the farewell in the
next slot forces the ending either way. `summary.md` counts slots 4 and 5
together.

## What was measured

Three full 34-pairing runs, one per wording. "Too early" means the persona hung
up on probes 1 to 3, before the concrete answer existed — the failure ADR 0037
calls the expensive one.

| | baseline | v1, imperative | v2, conditional | v3, gated |
|---|---|---|---|---|
| closed on the met condition (probe 4/5) | 0 | 1 | 4 | **6** |
| closed on the farewell (probe 6) | 28 | 0 | 14 | 18 |
| never, ended on a backstop | 6 | 1 | 6 | 9 |
| **too early (probe 1–3)** | **0** | **32** | **10** | **1** |

**v1** ended: "…accept it in your own words, thank them, and finish your reply
with exactly this marker and nothing after it: `[CALL_END]`." Nearest the reply,
that reads as an order and not as a condition, and the persona appended it to its
own opening question:

> "Could you please let me know if the original date is still confirmed …?
> Thank you for your time. Goodbye. `[CALL_END]`"

which is precisely what the system prompt forbids two paragraphs earlier. The
same recency that ADR 0038 exploited fires in the expensive direction just as
readily.

**v2** removed the marker from the nudge, put the open case first, and required
the persona to be able to quote back what met the criterion. That bought the
first real closings (0 → 4) at the cost of ten premature hang-ups — nine of them
on the user's *first* reply, where the trainee has said nothing substantive and
the check has one possible answer.

**v3** is v2 withheld until the persona's third reply. The premature endings drop
to one and the correct closings rise to six.

## Consequences

Six of 34, not thirty-four of 34. The prompt frame moves this from "never" to
"sometimes"; the rest is the model. The transcripts say why, and it is not an
information failure — on `deadline-correction` the persona *restates* the new
date, the partial delivery and the third-party appointment correctly, and then
asks the user to confirm them, twice in a row. Qwen3-4B can carry the facts and
cannot convert "I have all of it" into "so I am done". Three formulations bracket
that: made an order it fires everywhere, made a condition it barely fires at all.

Backstop endings rose from 6 to 9. Those are calls the repetition guard closed,
which is a worse ending than a clean one but not a broken call, and at n=34
against a non-deterministic model the difference is not clearly signal.

`backend/session/orchestrator.py` now carries two pylint exceptions it did not
have: the module passes 1000 lines, and the orchestrator holds an eleventh
instance attribute. Both are noted inline. The module is mostly prompt text with
the rationale for each guard beside it; splitting the text out would put that
rationale one file away from the code that sends it — worth doing, not worth
folding into this change.

## The fix this does not attempt

`force_end_call` plus `_CLOSING_NUDGE` is a *reliable* closer: in the baseline
run it ended 28 of 34 calls, cleanly, on demand. What is missing is not the
ability to close, it is the trigger — and the persona is the wrong thing to ask,
because it is the same 4B model that cannot make the judgement.

A second, small LLM call could: given the `success_condition` and the transcript
so far, has it been met? Answered outside the persona's turn — concurrently with
the next Turn's STT, so nothing lands on the latency path ADR 0033 exists to
protect — a "yes" would set `force_end_call` on the following Turn and go through
the closing path that already works. That is a larger change with its own
failure modes (a wrong "yes" ends a call the user was still in), and it should be
built against the numbers above rather than instead of them.
