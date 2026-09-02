# ADR 0051: Statistics Describe the Whole Session and Carry No Invented Norms

## Status

Accepted. Narrows ADR 0014 (which statistics), ADR 0047 (what is measured) and ADR 0048 (when it is evaluated).

## Context

ADR 0047 and ADR 0048 govern *how* and *when* measurement happens, not *what* a statistic is a statement about. The first working version answered that implicitly with "about a single utterance", because that is where the measurement takes place. Three problems followed.

**The frame of reference was too small.** Eight utterances yielded eight speaking rates whose spread is mostly the measurement noise of short samples. A share of the talking time is not defined over a single Turn at all. F-53 states the expectation as statistics *of a conversation*.

**The thresholds were invented.** Every "typically 100–180" came from the general literature or from a plausibility assumption, never from data about this group of users — and was presented to the user as a norm regardless.

**The machine's latency landed on the human.** Seconds pass in which nobody speaks; read naively they look like the user faltering. ADR 0042 sharpens this: the opening line is generated at connect but heard only after the setup screens, so a clock started at connect counts the user's time on those screens as their first reaction.

## Decision

- **Every statistic describes the whole conversation.** `Messung` and `Befund` hang off the `Session`, not the `Turn`, which keeps only its text and its position on the timeline.
- **The set of statistics is F-53's**, plus F-37's loudness curve. Pitch and voice-quality analysis (F-35, F-38) are not collected.
- **No statistic carries a target range.** No `Befund` rows are written, and the prompt forbids the model from judging a figure against a norm of its own. An invented threshold is a score in disguise, and contradicts ADR 0004.
- **Nothing is measured against the Persona.** The partner is a synthesized voice; comparing the user to it reports a TTS setting as though it described the user. F-36 asks for the speaking rate "relativ zum Gesprächspartner" — that waits until the partner is a person.
- **The machine's response time is charged to neither speaker.** Each speaker's window is tracked separately, and reaction time counted from the end of the Persona's utterance. The Session clock starts when the client reports it is playing the opening line, not at connect.

## Consequences

The user is given six figures without a verdict. What they mean is said in words by the wrap-up, which is what ADR 0004 asks for anyway.

F-35, F-38 and the derivation of `Befund` rows are deferred, not discarded. They are worth bringing back only with pilot recordings against which thresholds can be established; until then `Befund` has no writer and no reader, but the table stays, so turning it on is a code change rather than a migration.

Because `Messung` hangs off the Session, a statistic can no longer be traced back to one utterance, and the migration reverses that direction only lossily.

The Persona's speaking window is a model, not a measurement: it assumes the client plays back without gaps, and a client-side stall overestimates reaction time. Fixing that needs the client to report actual playback completion, which does not justify widening the protocol (ADR 0033) for one figure among six that carries no judgment.
