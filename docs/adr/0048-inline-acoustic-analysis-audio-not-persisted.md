# ADR 0048: Paraverbal Analysis Runs Inline on In-Memory Audio; Audio Is Never Persisted

## Status

Accepted. ADR 0051 keeps the measurement here but moves the *interpretation* to the end of the call: what is produced inline are raw per-Turn quantities, not finished statistics.

## Context

ADR 0034 left this open explicitly: it persists Session data but not Session audio, which makes paraverbal measurement impossible to recompute after the fact. "Either that analysis runs while the Session's audio is still in memory, or the audio must be handed to the async worker as part of its job payload."

Putting it in the worker means the job payload carries the audio. A five-minute Session is on the order of ten megabytes of speech, and Redis is a memory-resident store being used here as a broker.

Running it inline is constrained by the live path: ADR 0033 made the Session a streaming pipeline and Q-03 makes audible stalls a quality failure. What makes the question answerable is where the cost falls. Each Turn already blocks on one non-streamable STT round trip — hundreds of milliseconds on the network — while Praat's analysis of a Turn is tens of milliseconds of local computation. The two do not compete for the same resource.

## Decision

We will measure each Turn's paraverbal features inline, on a worker thread started when the STT request is issued and awaited after it returns. The audio is released as soon as the measurement completes; only the resulting numbers survive the Turn. Session audio is never persisted, never written to disk, and never placed on the queue — the worker receives a Session identifier.

A failure inside the measurement is not a pipeline failure. ADR 0016's retry-once-then-end policy governs the legs the conversation depends on; this is not one of them, so a Turn that cannot be measured contributes no numbers and the call continues.

## Consequences

The measurement runs concurrently with a network wait the Session was already paying for, so it costs no wall-clock time and Q-03 is untouched. That holds only while Praat stays fast relative to the gateway — the assumption to re-check if measurement ever grows more expensive.

Audio never leaves the process that recorded it, so the DSGVO surface ADR 0034 opened does not widen: what is retained is transcripts and numbers.

The seam between app and worker now follows a real difference in the work rather than a point in time. Measurement is deterministic, cheap and needs the waveform, so it belongs where the waveform is; interpretation is a slow, retryable model call that needs no audio.

Because the audio is gone once the Turn ends, a metric added later cannot be backfilled. Every new metric starts producing data on the day it ships. That is the direct cost of not storing audio, accepted for the same reason ADR 0034 accepted losing an abandoned Session: the alternative is a voice archive the MVP has no consent story for.
