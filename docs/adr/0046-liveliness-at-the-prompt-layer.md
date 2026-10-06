# ADR 0046: Liveliness Is Pursued at the Prompt Layer Before the Turn-Taking Layer

Proposed, not agreed.

## Context

The counterpart sounds like a system answering: flat delivery, no emotional arc, and it never interrupts or backchannels. Three layers could carry liveliness: the prompt, the prosody (TTS parameters per chunk), and turn-taking. Turn-taking would rework the barge-in model (ADR 0035/0036).

## Decision

Pursue liveliness in the prompt first. Prosody stays open but unscheduled. Turn-taking is out of scope until the prompt layer is exhausted.

## Consequences

Attempts stay cheap and reversible, but are capped by the model. The counterpart still always waits its turn. Liveliness cannot be measured, so any improvement is a judgement.
