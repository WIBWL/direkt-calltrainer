# ADR 0032: AnalysisJob as a Persisted Entity for Async Job Status

## Status

Accepted

## Context

ADR 0018 decoupled Feedback/wrap-up generation into an async worker consuming a `SessionCompleted` job off a queue (ADR 0019: Redis + RQ), and ADR 0016 defined a retry-once-then-end-Session policy for pipeline failures. Neither, on its own, gives a durable, queryable record of what happened to a given Session's async processing after the fact — Redis/RQ's own queue state does not survive independently of the queue and isn't something the rest of the application can easily read.

## Decision

We added `AnalysisJob` as its own table: one row per async job (`kind`: analysis or feedback) tied to a Session, tracking `status` (queued, running, done, failed), an `attempts` retry counter, `error_text` on failure, and `updated_at`. This is a persisted status record, distinct from Redis/RQ's own in-flight queue state (ADR 0019) — the queue is where jobs execute, this table is where their outcome is durably recorded.

The transitions have one owner, `backend/feedback/jobs.py`, with two writers distinguished by whether they are the process doing the work. The worker's writer runs inside the caller's transaction and overwrites whatever state it finds, because it is the process running the job; the whole of generation and storage sits inside its failure boundary, so a storage failure closes the row rather than leaving it at running. The other writer opens its own transaction, for callers that can only observe from outside that the work will not happen — the enqueue to Redis failing after the Session was committed. Not running the job, it leaves `done` and `failed` alone: by the time it commits, the wrap-up may already be on the user's screen.

## Consequences

Session processing status and history can be queried from Postgres alone, without reaching into Redis, and survives Redis restarts or queue eviction — useful both for user-facing "did feedback ever get generated" checks and for ADR 0016's retry logic to have a durable attempt counter. This does mean job status has to be kept in sync in two places: the RQ job's actual execution state and this row. Every path that can strand a row closes it, which narrows the window in which the two disagree without removing it — a worker killed between marking running and finishing leaves a row nothing will correct. Reconciling those needs a sweep that can tell a dead worker's job from a live one's, which a single process cannot do by reading this table alone, and which is left undone rather than done wrongly.
