# ADR 0051: Statistics Describe the Whole Session and Carry No Invented Norms

## Status

Accepted. Narrows ADR 0014 (which statistics), ADR 0047 (what is measured), ADR 0048 (when it is evaluated) and ADR 0026 (what a statistic hangs off). Amended by ADR 0078 and ADR 0081, each on one point, and it is worth being precise about which: the rule below is "no statistic carries a target range", and it stands under both.

**ADR 0081** narrows the first bullet. A statistic still describes a stretch of conversation and never a single utterance, but "the whole call" is no longer the only stretch: the same metrics are also measured over the exchanges where the partner pushed back and over the remainder, so that F-62's "Souveränität unter Druck" rests on a measurement. Two things make that a narrowing rather than a reversal. The raw facts now kept per utterance (`turn.acoustics_json`) are *facts and not statistics* — nothing derived, nothing shown — and they exist because the audio is discarded when the call ends (ADR 0048) while the split is decided afterwards. And nothing compares the two figures: no difference, no index, no verdict, because how large a gap means something is exactly the norm this ADR refuses to invent. ADR 0078 permits a colour on a *classification* whose whole scale is shown to the user in the unit they are reading, which is the opposite case from the invisible band behind a raw figure that this ADR was written against. `metric_type` still has no target column, no `Finding` row is written from a threshold, and the prompt still forbids the model judging a figure against a norm of its own.

## Context

ADR 0047 and ADR 0048 govern *how* and *when* measurement happens, not *what* a statistic is a statement about. The first working version answered that implicitly with "about a single utterance", because that is where the measurement takes place. Four problems followed.

**The frame of reference was too small.** Eight utterances yielded eight speaking rates whose spread is mostly the measurement noise of short samples. A share of the talking time is not defined over a single Turn at all. F-53 states the expectation as statistics *of a conversation*.

**The thresholds were invented.** Every "typically 100–180" came from the general literature or from a plausibility assumption, never from data about this group of users — and was presented to the user as a norm regardless.

**The two speakers are not measured the same way.** Praat's silence segmentation gives the user's audio twice over: its full length, and the phonation time left once the silences are removed. The Persona has only the first, modelled from the duration of the audio synthesized for it. A share between the two speakers therefore has one honest pair of terms, and a rate over one speaker has a different one.

**The machine's latency landed on the human.** Seconds pass in which nobody speaks; read naively they look like the user faltering. ADR 0042 sharpens this: the opening line is generated at connect but heard only after the setup screens, so a clock started at connect counts the user's time on those screens as their first reaction.

## Decision

- **Every statistic describes the whole conversation.** `Measurement` and `Finding` hang off the `Session`, not the `Turn`, which keeps only its text and its position on the timeline.
- **The set of statistics is F-53's**, plus F-37's loudness curve. Pitch and voice-quality analysis (F-35, F-38) are not collected.
- **No statistic carries a target range.** No `Finding` rows are written, and the prompt forbids the model from judging a figure against a norm of its own. An invented threshold is a score in disguise, and contradicts ADR 0004.
- **A share divides audio duration by audio duration; a rate divides by phonation.** F-24's talk share compares the length of the user's recording with the length of the Persona's synthesized audio, because that is the only quantity both sides have. F-36's speaking pace divides by phonation, so it says how fast the user talks rather than how much of the call they filled. The Turn carries both, under names that say which is which.
- **A statistic whose measurement failed is omitted, not estimated.** An unmeasured Turn (ADR 0048) still contributes its words, so talk share and speaking pace would come out short by an unknown amount; they are withheld for the whole call instead. Reaction time is sampled only from Turns with a measured start, since an unmeasured one falls back to the end of the user's speech and would read as hesitation the length of the utterance. word count and questions never needed the audio and are unaffected.
- **Nothing is measured against the Persona.** The partner is a synthesized voice; comparing the user to it reports a TTS setting as though it described the user. F-36 asks for the speaking rate "relativ zum Gesprächspartner" — that waits until the partner is a person.
- **The machine's response time is charged to neither speaker.** Each speaker's window is tracked separately, and reaction time counted from the end of the Persona's utterance. The Session clock starts when the client reports it is playing the opening line, not at connect.

## Consequences

The user is given six figures without a verdict. What they mean is said in words by the wrap-up, which is what ADR 0004 asks for anyway.

Withholding is visible: a call with one unmeasurable Turn shows four figures instead of six, with no explanation of the gap. That is the same trade as the missing target ranges — a figure the user cannot tell from a measured one is worse than none — but it is blunt, since one failed Turn in twenty suppresses both acoustic statistics. Excluding only that Turn's words would be finer, and is worth revisiting if the pilot shows measurement failures are common rather than rare.

F-35, F-38 and the derivation of `Finding` rows are deferred, not discarded. They are worth bringing back only with pilot recordings against which thresholds can be established; until then `Finding` has no writer and no reader, but the table stays, so turning it on is a code change rather than a migration.

Because `Measurement` hangs off the Session, a statistic can no longer be traced back to one utterance, and the migration reverses that direction only lossily.

The Persona's speaking window is a model, not a measurement: it assumes the client plays back without gaps, and a client-side stall overestimates reaction time. Fixing that needs the client to report actual playback completion, which does not justify widening the protocol (ADR 0033) for one figure among six that carries no judgment.
