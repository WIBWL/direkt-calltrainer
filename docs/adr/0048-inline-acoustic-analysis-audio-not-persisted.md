# ADR 0048: Paraverbal Analysis Runs Inline on In-Memory Audio; Audio Is Never Persisted

## Context

Putting acoustic analysis in the worker would put megabytes of audio on Redis. Inline, Praat's tens of milliseconds per Turn overlap the STT round trip the Turn already waits for.

## Decision

Each Turn is measured on a worker thread started alongside the STT request. The audio is released when the measurement ends and is never stored, written to disk or queued. A failed measurement is not a pipeline failure: the Turn records that it was not measured, so its transcript is not read as words spoken in no time.

## Consequences

Measurement costs no wall-clock time while Praat stays fast. Only transcripts and numbers are retained. **A metric added later cannot be backfilled**; each starts collecting on the day it ships.
