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
