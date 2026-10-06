# ADR 0079: Whether the Tone Suited the Occasion, as Prose

## Context

The intonation page kept saying that the right delivery depends on the occasion, while the app knew the occasion and said nothing about it. A per-category norm would be invented four times over.

## Decision

- The wrap-up writes one paragraph, `feedback.tone_fit`, on whether the delivery suited this call's occasion, in the same model call.
- The prompt is given the Scenario's description and the caller's goal, with the success criterion cut off (the "The matter is settled when" sentence), because that is a result, not an occasion. A test checks the seed convention the cut relies on.
- Rules: start from the occasion, not the figures; there is no correct register for a kind of call; "it suited" is a normal answer; quote the transcript; don't restate `phase_language`.
- It is shown on the intonation page, visibly set apart as the model's reading, not a measurement.

## Consequences

The gap F-35 kept naming is closed. It is the weakest claim on that page and is presented as such. The wrap-up prompt grows again.
