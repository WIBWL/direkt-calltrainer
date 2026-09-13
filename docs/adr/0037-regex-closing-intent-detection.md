# ADR 0037: Closing-Intent Detection Is Regex-Based, Not an LLM Classifier

## Status

Accepted

## Context

The persona is expected to end the call itself when the user signals it's over (a goodbye, or a request to postpone/continue elsewhere), but the small dialogue model (Qwen3-4B) frequently failed to recognize indirect signals ("können wir das Gespräch woanders fortsetzen"), even with an explicit ending instruction in its own system prompt. A first regex/keyword-based farewell detector was replaced with a full LLM semantic classifier — a separate chat-completion call per Turn, with an explicit chain-of-thought reasoning step — to close that recall gap. In production use the classifier turned out to be unreliable in the opposite direction: its own reasoning step would occasionally degenerate into a sentence unrelated to what the user actually said, and still confidently conclude "yes" — ending calls mid-conversation while the user was still actively engaged (e.g. asking a clarifying question).

## Decision

We reverted closing-intent detection to a deterministic regex check, scoped narrowly to two concrete categories observed to actually need it: explicit farewells ("tschüss", "auf wiederhören", …) and requests to postpone/continue elsewhere ("ein anderes Mal", "melde mich später", …). It runs against the latest user message only, with no LLM call involved.

## Considered Options

- **Trust the persona's own system-prompt instruction to end the call.** The prompt already tells the persona to close when the user signals it is over. Rejected on its own: Qwen3-4B misses indirect signals ("können wir das woanders fortsetzen") often enough that a call would drag on past a clear goodbye. It is kept as the backstop behind the regex, not the primary mechanism.
- **A dedicated LLM semantic classifier (a chat-completion call per Turn with a chain-of-thought step).** This was actually built and shipped. Rejected after production use: the reasoning step would occasionally wander to a sentence unrelated to the user's message and still conclude "yes", cutting a call short mid-conversation — a high-cost failure that a deterministic check cannot produce.
- **Keyword list without regex structure.** Rejected: the postpone/continue-elsewhere category needs light phrasing tolerance (word order, filler) that a flat `in` check does not give, and the regex is still trivially auditable.

## Consequences

A missed signal (a phrasing the regex doesn't cover) costs at most one extra Turn before the persona's own closing judgment, still driven by its system prompt, catches up — a minor, low-cost failure. A false positive under the LLM classifier cut a call short mid-conversation — a high-cost failure that directly undermines the training experience. This asymmetry is why the regex's known lower recall was judged an acceptable trade for its determinism, even though that same brittleness to phrasing variety was the original reason it was replaced once already. Expanding this regex's phrase coverage over time is the intended way to close remaining gaps, not reintroducing a classifier call.

## Amendment (2026-09-06): the persona's own `[CALL_END]` is vetoed while it is still pressing

The other direction of the same asymmetry showed up live: the model ended a call by itself — `[CALL_END]` straight after "Ich will wissen, was los ist und wann die Problematik behoben wird." — twice in one session, with the demand wide open and no goodbye, which the trainee heard as the caller hanging up on them. The system prompt already forbids exactly this ("never in the same reply as a question or a statement that the issue isn't resolved"), and the 4B model does it anyway.

So the marker is trusted only where it was asked for. On a Turn the closing nudge sent (the user said goodbye or asked to postpone — the regex above fired), the model's `[CALL_END]` is taken at its word. Anywhere else it is the model's own idea, and it is ignored when the reply's last sentence is still pressing: it ends in a question mark, or matches a new per-language `still_pressing_re` in the language pack ("ich will/muss wissen", "wann wird …", "ich warte auf …" and the English shapes) — unless the reply carries a farewell anywhere, which wins outright ("ich brauche nichts weiter, auf Wiederhören"). The farewell decides rather than the last sentence's shape because `docs/research/model-parameters.md` had already measured, and rejected, a plain "ignore the marker if the reply contains `?`" rule: half of the legitimate endings finish on a trailing question after the goodbye ("Auf Wiederhören. Darf ich mich melden?"). A vetoed marker is logged; the reply is spoken and the call goes on. Same discipline as the user-side patterns: narrow, regex, auditable, and grown from observed calls. The cost of a missed veto is an abrupt ending, of a false one a call that runs one Turn longer — so the pattern errs toward vetoing.

Found in the same session and fixed alongside: the chunker flushes at sentence ends, so a marker mid-chunk dragged the model's *next* sentence along, and merely deleting the marker had that sentence read out after the goodbye. The chunk is now cut at the marker.

## Amendment 2026-09-08: a goodbye without the marker also ends the call

The veto above assumes the failure runs one way — a marker where there should be none. Running the dialogue on a stronger model (ADR 0074) surfaced the opposite, and it is not carelessness but obedience.

Observed live: the persona replied *"Eine Bestätigung per E-Mail reicht allein nicht, wenn die Daten bis dahin nicht tatsächlich wieder fehlerfrei fließen … Sollte es dann immer noch zu Fehlern kommen, müssen wir die Geschäftsführung direkt in die Verantwortung nehmen. Ich danke Ihnen für die Klärung … Auf Wiederhören."* — and emitted no `[CALL_END]`. The trainee heard the caller hang up and had to end the Session by hand.

Three things were ruled out by measurement before anything was changed. The veto did not fire: the log carries no "unprompted `[CALL_END]` … ignored" line. The reply was not truncated: it is ~121 tokens against a 180-token cap. And the model does emit the marker when a call ends cleanly — four of four replays of a settled closing exchange carried it. What the reply actually did was follow the system prompt, which says never to put the marker in a reply that also states the matter is not resolved. It voiced a reservation, so it withheld the marker, and then said goodbye anyway.

So `_commit_reply` ends the call when the persona's committed reply carries a farewell and no marker, using the same `farewell_re` that already overrules `still_pressing_re` — both directions therefore read a goodbye identically. The fallback closing line is deliberately *not* spoken on this path: the persona has just said its own, and adding one would say it twice.

The prompt is left alone. Its rule is right — a marker on an unresolved reply is what the veto exists to catch — and the model followed it. The gap was in the code that reads the reply, not in the instruction that produced it.
