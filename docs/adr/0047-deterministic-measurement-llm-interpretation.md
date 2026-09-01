# ADR 0047: The Model Interprets Measurements, It Does Not Produce Them

## Status

Accepted

## Context

ADR 0003 makes Feedback fully AI-generated; ADR 0004 requires it to be qualitative and traceable rather than a score; F-10 requires improvement suggestions to refer to concrete points in the conversation. ADR 0003 also names the risk: Feedback quality depends entirely on the AI, with no human fallback to correct a misjudgment.

The model behind this is a small, university-hosted model (ADR 0011), already documented in this codebase as unreliable at exactly this kind of task — ADR 0037 rejected it as a classifier, ADR 0038 had to guard against it repeating itself. Asked to assess speech from a transcript, a model of that calibre will invent quantities it has no way of knowing: a tempo in words per minute, a count of filler words.

ADR 0046 means those quantities now genuinely exist as rows before any prompt is built. The question is what the model is asked to do with them.

## Decision

We will split the wrap-up into a measurement half and an interpretation half, and give the model only the second. Every number originates from Praat (ADR 0045) or the transcript, is computed before the model is called, and is passed into the prompt as a stated fact. The model is instructed to interpret those findings and explicitly not to estimate, recompute, or introduce quantities of its own.

The model returns structured output: a summary plus a list of points, each optionally carrying the `turn_id` it refers to. That reference is what makes ADR 0004's traceability real rather than aspirational. A point citing a Turn outside this Session keeps its text and loses the citation.

`Feedback.score` stays null. ADR 0004 permits a supplementary numeric score and F-14 lists it as COULD; we do not populate it in the MVP.

## Consequences

The part of the Feedback that can be objectively wrong is no longer produced by a language model. A user who disputes a claim about their speaking tempo can be shown the measurement it came from. The subjectivity risk ADR 0003 records is not eliminated, but it is confined to the wording rather than extending to the facts.

Structured output is a harder ask of this model than free prose, and the degradation path is real: a response that never validates yields a summary with no evidence links. That is a deliberate trade against showing the user nothing.

The design puts a ceiling on what the wrap-up can say. The model can only discuss what was measured, so a communication problem no metric captures is one the Feedback will not raise. Broadening it means adding metrics, not loosening the prompt — the quality of the Feedback is now bounded by the metric inventory rather than by the model's fluency.
