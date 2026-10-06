# ADR 0081: Measurements Over the Demanding Stretches of a Call

## Context

"Souveränität unter Druck" asks whether delivery holds up when the partner pushes back. Whole-call figures average both stretches together. Whether an exchange was demanding is a judgement about content, the audio is gone by the time anyone can make it, and the wrap-up is the only reader of content.

## Decision

- **The wrap-up marks the stretches.** `pressure_turns` lists the partner lines that put the trainee under pressure (objection, complaint, refusal, demand, challenge, repeated ask), never a neutral question. An empty list is a normal answer. Foreign ids are dropped.
- **A user utterance belongs to the stretch of the line it answers.** A test pins this.
- **Each user utterance keeps its raw acoustic facts** (`turn.acoustics_json`: speaking time, phonation, pauses, loudness slice), so the split can be computed after the audio is gone. These are facts, never statistics shown to anyone.
- Talk share, pace, pauses, run length and loudness are measured again over `pressure` and `rest` (`measurement.segment`). A segment with fewer than three user utterances is not measured. Whole-call rows are never rewritten. Segment storage is idempotent and has its own failure boundary.
- **Nothing compares the two figures**: no difference, ratio, colour or word like "stable". The interface says the split was made by a model.

## Consequences

The goal has a measurement, the first that describes a *part* of a call. The split is only as good as the model, and a run that marks everything or nothing looks healthy anyway; `inspect_pressure_segments` exists to check it. A model that drops the key costs the comparison silently.
