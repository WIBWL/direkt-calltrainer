# ADR 0032: AnalysisJob as a Persisted Entity for Async Job Status

## Status

Accepted

## Context

ADR 0018 decoupled Feedback/wrap-up generation into an async worker consuming a `SessionCompleted` job off a queue (ADR 0019: Redis + RQ). That queue, on its own, gives no durable, queryable record of what happened to a given Session's async processing after the fact — Redis/RQ's own state does not survive independently of the queue and isn't something the rest of the application can easily read.

## Decision

We added `AnalysisJob` as its own table: one row per async job (`kind`: analysis or feedback) tied to a Session, tracking `status` (queued, running, done, failed), an `attempts` counter, `error_text` on failure, and `updated_at`. This is a persisted status record, distinct from Redis/RQ's own in-flight queue state (ADR 0019) — the queue is where jobs execute, this table is where their outcome is durably recorded.

Only `feedback` rows are ever written. The `analysis` kind stays in the vocabulary but is inactive for good: since ADR 0047/0048 the acoustic analysis runs inline in the live path and is persisted synchronously with the Session (`session/persistence.py`), so it never was a job and will not become one. The value is left in the CHECK constraint rather than migrated away, the way `Finding` and the inactive `phase_appropriate_language` metric are left in place — a documented dead value costs less than a migration for cosmetics.

The transitions have one owner, `feedback/jobs.py`, with two writers separated by whether they are the process doing the work. The worker's writer runs inside the caller's transaction and overwrites whatever state it finds; the whole of generation *and* storage sits inside its failure boundary, so a wrap-up that is generated but cannot be written closes the row rather than leaving it at `running`. The other writer opens its own transaction, for a caller that can only observe from outside that the work will never happen. Not running the job, it leaves `done` and `failed` alone — by the time it commits, the wrap-up may already be on the user's screen — and it never raises, because every caller it has is already handling a failure of its own.

## Consequences

Session processing status and history can be queried from Postgres alone, without reaching into Redis, and survive Redis restarts or queue eviction. The row is written `queued` in the same transaction as the Session (`session/persistence.py`), moved to `running`, `done` or `failed` through `feedback/jobs.py`, and read by `_feedback_status` in `api/sessions.py` — that is the `status` field the post-call screen polls on until the wrap-up settles (ADR 0050).

`attempts` and `error_text` have no reader in the application: they exist for whoever is looking at a failed Session in `psql` afterwards, which is the durable-record purpose above. `attempts` therefore stands at 1 after a normal run. It is explicitly not the counter behind ADR 0016 — that retry policy governs the live STT/LLM/TTS pipeline, which never touches this table; the wrap-up's own retry lives inside one `generate_feedback` call (`_ask`) and does not write the row.

The cost stays as stated: job status lives in two places — the RQ job's actual execution state and this row — and only the failures one side can prove are carried across. A failed enqueue is one: `api/session_ws.py` knows there that no worker ever received the job, so it fails the row itself (`jobs.mark_failed`) rather than leave it at `queued`; nothing downstream could, because nothing downstream exists. A worker killed mid-job is not: its row stays `running` for good, so `api/sessions.py` reads a `running` row older than the queue's `JOB_TIMEOUT_S` as failed instead of leaving the client spinning. That is a judgement at read time and not a repair — the row itself still says `running`. A reaper that would heal it is deliberately not built: it would be a second scheduled process for a table nothing else queries.
