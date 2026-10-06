# ADR 0051: Statistics Describe Stretches of Conversation and Carry No Invented Norms

## Context

Per-utterance figures were mostly noise. Thresholds like "typically 100–180" were invented, not drawn from these users. The two speakers are not measured alike, and the machine's latency looked like the user hesitating.

## Decision

- **A statistic describes a stretch of conversation, never one utterance:** the whole call, and also the demanding stretches and the rest (ADR 0081). `Measurement` hangs off the Session.
- **No statistic carries a target range.** No `Finding` is written from a threshold, and the prompt forbids the model judging a figure against a norm. A traffic light on a classification is allowed only under ADR 0078.
- **A figure whose measurement failed is omitted, never estimated.**
- **Nothing is measured against the Persona**, whose voice is a TTS setting.
- **The machine's response time is charged to neither speaker.** Reaction time runs from the end of the Persona's audio to the user's first sound. The Session clock starts when the client plays the opening.
- A share between speakers uses each side's span of speech (ADR 0114); a rate over the user divides by phonation.

## Consequences

Users get figures without a verdict, and the wrap-up says what they mean. One unmeasurable Turn withholds the acoustic figures for the whole call. `Finding` stays in the schema without a writer.
