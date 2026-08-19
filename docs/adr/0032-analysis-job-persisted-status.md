# ADR 0032: AnalysisJob as a Persisted Entity for Async Job Status

## Status

Accepted

## Context

ADR 0018 decoupled Feedback/wrap-up generation into an async worker consuming a `SessionCompleted` job off a queue (ADR 0019: Redis + RQ), and ADR 0016 defined a retry-once-then-end-Session policy for pipeline failures. Neither, on its own, gives a durable, queryable record of what happened to a given Session's async processing after the fact — Redis/RQ's own queue state does not survive independently of the queue and isn't something the rest of the application can easily read.

## Decision

We added `AnalysisJob` as its own table: one row per async job (`art`: analyse or feedback) tied to a Session, tracking `status` (queued, running, done, failed), a `versuche` retry counter, `fehlertext` on failure, and `aktualisiert_am`. This is a persisted status record, distinct from Redis/RQ's own in-flight queue state (ADR 0019) — the queue is where jobs execute, this table is where their outcome is durably recorded.

## Consequences

Session processing status and history can be queried from Postgres alone, without reaching into Redis, and survives Redis restarts or queue eviction — useful both for user-facing "did feedback ever get generated" checks and for ADR 0016's retry logic to have a durable attempt counter. This does mean job status now has to be kept in sync in two places: the RQ job's actual execution state and this row. The worker code responsible for writing these transitions was not part of this persistence-layer change and is not yet implemented.
