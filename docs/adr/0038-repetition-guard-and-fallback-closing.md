# ADR 0038: Guard Against Degenerate Repetition; Guarantee a Closing Line on Backstopped Endings

## Status

Accepted

## Context

In testing, the small dialogue model would occasionally degenerate: repeating its own previous reply near-verbatim across Turns, or repeating a sentence within a single reply. Separately, a call can end via three different paths — the model's own `[CALL_END]` marker after being explicitly nudged (ADR 0037's closing check firing), the model including that marker completely unprompted, or (new here) a detected repetition — and only the nudged path actually asked the model to produce a goodbye line, so the other two paths could not be trusted to end with one.

## Decision

A reply that shows any of the following is treated as an implicit signal that the call should end, on the reasoning that a model looping has nothing further to contribute:

- **repeats one of its own sentences** within itself;
- **is verbatim the immediately preceding reply** (case/whitespace-insensitive), at any length — an exact back-to-back repeat is degenerate however short it is;
- **is verbatim a reply from further back than the previous Turn** — the model tends to oscillate (A-B-A-B), where the repeat is two Turns back and a "same as last reply" check walks straight past it; this one carries a short-acknowledgement length floor, since a brief line ("Ja, genau.") can legitimately recur across a longer call;
- **restates most of the previous reply** — more than half of its comparable sentences were already there. The verbatim checks never fire in practice because the persona varies its opening sentence and carries the same block underneath it Turn after Turn, so what separates a loop from a caller legitimately quoting a figure twice is *how much* of the reply is old, not *whether* a sentence came back.

Whenever a call ends via the repetition path, or via an unprompted `[CALL_END]` that was never nudged, a fixed, pre-written German closing line is synthesized and appended instead of relying on whatever the model actually produced on those paths.

## Consequences

Every ended call now reliably closes with an audible, on-brand sign-off regardless of which path triggered the ending, and a degenerate repetition loop — verbatim, oscillating, or a fresh-worded restatement of the same content — is cut short rather than continuing indefinitely or requiring the user to end the session manually. The trade-off is a small added latency and one extra synthesized utterance specifically on backstopped endings, and the checks remain heuristics: the share threshold is tuned against a handful of real calls (a restatement measured ~80%, a reply that moved the call on ~25%), so a reply that reworks the same content into all-new sentences, or restates a reply from several Turns back rather than the immediately previous one, can still slip through.

## Amendment (2026-09-03): re-introduction, a per-turn nudge, and regenerate-before-end

Pilot feedback: the persona repeated itself audibly and often — most visibly by reading its own introduction back out on the first turn or two ("Guten Tag, ich bin Thomas Brandt, …" a second time), and by re-emitting a whole demand verbatim when the trainee stalled. Two gaps behind this:

- The decision above turns **every** detected repeat into an end-of-call. For a whole verbatim repeat that is defensible, but a re-introduction is not "nothing left to say" — it is the model losing its place — and ending the call there makes for a very short exercise whenever a beginner stalls.
- Live testing against `Qwen3-4B-AWQ` confirmed `presence_penalty` (the parameter the model card recommends, already set) does **not** stop the model repeating a full paragraph once the conversation has nothing new in it, and that the standing "never repeat yourself" line in the system prompt is too far up-context to bite on its own. (`docs/research/model-parameters.md` already recorded the first half of this.)

Repetition is now fought on three fronts, cheapest first:

1. **Prompt.** The frame states plainly that the call was already opened: no greeting again, no name again, no laying out the reason as if for the first time.
2. **A per-turn nudge.** Every turn past the opening carries a transient system message quoting the persona's *own last reply* verbatim, telling it to say something new. Not stored in history. In testing this took verbatim whole-reply repeats from ~4-in-7 stalling turns to ~0.
3. **Regenerate before ending.** A reply whose **first chunk** opens with a greeting again (matched by a new `regreeting_re` in the language pack, and only once the call is under way) raises out of the stream *before any audio is synthesized*; `_generate_reply` re-asks the model once with an explicit nudge quoting the rejected opening, and the call carries on. This is deliberately narrow — a greeting at the very start of a reply, paired with the persona re-naming itself or the opening's wording carried over — so it does not disturb the verbatim / oscillation / restatement checks, which stay exactly as above and still end the call (the reply was already spoken, so there is nothing to regenerate).

**Requested repetition.** If the user's own turn asks the persona to say something again — "wer sind Sie nochmal?", "können Sie das wiederholen?", "das habe ich nicht verstanden", and the English equivalents (a fourth language-pack pattern, `repeat_request_re`, matched against the user's speech like the closing patterns) — repeating *is* the answer, but not a licence to parrot:

- the anti-repeat nudge is swapped for a **clarify nudge**: *say the same thing again, reworded — shorter, plainer, one or two sentences, not word-for-word*;
- the re-introduction guard and the cross-turn verbatim/restatement checks stand down **for that reply against the immediately-previous one only** — a verbatim re-dump of an *older* reply, and a sentence stuttered within one reply, still count;
- this exemption applies to the **first** repeat-request turn in a row. Ask a second time and the nudge hardens (*ask which part is unclear, or give the one key point and move on*) and the full guards are back, so a persona that just keeps re-reading the same block gets stopped.

This came from two real pilot failures. First: the user asked "wer sind Sie nochmals?", the persona correctly repeated its introduction, and the old guard read that as a loop and **ended the call**. Second: after a barge-in the user said "was haben Sie gesagt? nicht verstanden", and the persona re-delivered its entire previous paragraph verbatim, three turns running.

The barge-in half of that second failure is [ADR 0035](0035-barge-in-interruption.md)'s: a sentence the user heard 88% of was scored unheard, the Turn reopened, and the next reply restated everything from the top. Fixed there by `_HEARD_FRACTION` — a chunk played most of the way through now counts as heard, so the Turn closes and the user's reaction starts its own Turn instead of being merged into the interrupted one.

Consequences: the re-introduction the pilot complained about is gone at the source (prompt) and caught before it is heard (regeneration) if it slips through; reworded mid-call restatements are markedly rarer (nudge) and still end the call if one gets through (unchanged backstop); a repeat the user asked for is answered with a shorter rephrasing rather than the same wall of text, and asking repeatedly no longer loops forever. Costs: ~50–80 extra prompt tokens per turn for the nudge (negligible against a ~1.5k system prompt), and one extra LLM completion — no extra audio — on a turn that trips the re-introduction guard. The narrow guards still miss a re-introduction that does not start with a recognised greeting token, and a repeat-request phrased outside the pattern; both fall back to the unchanged post-hoc checks.
