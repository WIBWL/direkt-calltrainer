# ADR 0032: AnalysisJob as a Persisted Entity for Async Job Status

## Context

RQ's own state is neither durable nor readable by the application.

## Decision

`AnalysisJob` records one wrap-up job per Session: `status` (queued, running, done, failed), `attempts`, `error_text`, `updated_at`. Only the `feedback` kind is written; `analysis` stays an inactive vocabulary value.

- The row is written `queued` in the same transaction as the Session.
- One module owns the transitions. The worker's writer runs inside its own transaction and covers generation and storage, so a wrap-up that cannot be written still closes the row. The observer's writer (a failed enqueue) never overwrites `done` or `failed` and never raises.
- A `running` row older than the queue's job timeout reads as failed. It is not repaired.

## Consequences

The polled wrap-up status comes from Postgres alone. Job state lives in two places, and only provable failures cross between them. `attempts` and `error_text` are for whoever investigates in `psql`.
