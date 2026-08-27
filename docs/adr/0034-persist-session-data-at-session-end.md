# ADR 0034: Session Data Is Persisted in the MVP, Written Once at Session End

## Status

Accepted (supersedes ADR 0023)

## Context

ADR 0023 decided that no Session data would be persisted for the MVP: audio, transcripts, and Feedback were to live only in the memory of the running processes and be discarded once a Session ended, with consent-gated storage deferred until after the MVP. That decision was taken before the persistence layer existed.

Since then it does exist. ADR 0010 established an in-repo PostgreSQL instance, and ADRs 0025 through 0032 designed and built a complete normalized schema for Sessions, Turns, measurements, findings, and Feedback, with Alembic migrations and seeded reference data. None of it is reachable from the application: no code path in `backend/app.py` or `backend/api/session_ws.py` opens a database session, because ADR 0023 forbids precisely that. The result is a schema that has never had a row inserted by the product, and therefore has never been validated against how the Session pipeline actually produces data.

Several forces now pull against ADR 0023. F-12 (Aufzeichnung des Gesprächs) is a MUST feature and asks for the transcript to be available for later reflection, which an in-memory-only Session cannot offer beyond the browser tab that produced it. F-13 and F-48 need data spanning several Sessions and are impossible by construction. The async Feedback worker of ADR 0018/0019 has nowhere to write its result, and ADR 0032's `AnalysisJob` table describes job outcomes for jobs whose Session does not exist in the database.

At the same time, the live Session path constrains *how* data may be written. ADR 0033 made that path a streaming, real-time audio pipeline, and `backend/db/session.py` provides a synchronous SQLAlchemy engine. A blocking database call inside the turn loop would stall the event loop that is concurrently streaming synthesized audio, which is audible to the user and affects every Session sharing the worker process (Q-03). The Session orchestrator, however, already retains the complete Session in memory for the duration of the call, so nothing about the pipeline requires writing incrementally.

The MVP is operated with the project team and the two pilot companies, and has no user accounts: ADR 0009's Keycloak integration is not built and ADR 0031 leaves `subject_id` a pseudonym with no referential integrity behind it.

## Decision

We will persist Session data in the MVP, and we will write it exactly once, at the end of a Session, in a single transaction.

Persisted are Session metadata, the Turn transcripts, and — once the async worker of ADR 0018 exists — the measurements, findings, and Feedback belonging to that Session. Session audio is not persisted. ADR 0010 already keeps large files out of this database, and the schema (ADR 0026) has no column for a recording; a Session's audio therefore continues to exist only for as long as the Session is running.

The write happens after the Session has ended, at the point where the completed transcript is assembled for the client, and never during the live turn loop. Because the ORM session is synchronous and the surrounding path is asynchronous, the write is dispatched off the event loop rather than awaited inline. A Session that ends because the client disconnected is not persisted; only Sessions that reach a regular end — the user ending the call, the Persona ending it, or a pipeline failure per ADR 0016 — produce a row.

`subject_id` remains the pseudonymous placeholder of ADR 0031. This ADR does not revive ADR 0009 as a precondition and does not introduce an account concept.

What this ADR keeps from ADR 0023 is its commitment for the state *after* authentication exists: consent remains the sole basis on which a Session is tied to an identified User, and Users retain full self-service control over deleting their own data. For the MVP, where no account and therefore no in-system consent exists, F-49's data-protection notice before the first recording is a precondition for use rather than an optional feature, and the pilot group is informed out of band about what is stored.

## Consequences

The persistence schema stops being unexercised code. Its first real writer will surface the mismatches that a schema built ahead of its caller inevitably contains — among them `turn.start_offset_ms` and `turn.dauer_ms`, which are `NOT NULL` although neither the orchestrator nor the WebSocket protocol carries timing data today, and the divergence between the in-memory Turn (one exchange, comprising both speakers) and the persisted Turn (one utterance of one speaker). These are now blocking work items rather than latent surprises.

Writing once at the end keeps the real-time path entirely free of database dependencies. The live loop cannot fail because of the database, and a database outage degrades to "the Session ran but was not recorded" instead of breaking the call itself. The cost is symmetrical and deliberate: a user who closes the tab mid-call leaves no record at all, and the loss is unbounded within that one Session rather than limited to its last turn. For training data this is an acceptable trade; it would not be for anything the user is told was saved during the call, so the UI must not promise otherwise.

Because no audio is persisted, any analysis that needs the waveform — the paraverbal measurements of F-35 through F-38 and F-51, which ADR 0026 models as `Messung` and `Befund` rows against a Turn — cannot be recomputed after the fact. Either that analysis runs while the Session's audio is still in memory, or the audio must be handed to the async worker as part of its job payload. This is a genuinely open design question that ADR 0018's worker will have to answer, and it did not previously have to be asked, since nothing was stored at all.

The MVP now has a retained-data DSGVO surface where ADR 0023 deliberately had none. A retention period and a working deletion path become open obligations rather than deferred ones, and they are not satisfied today: the schema's cascades are declared only at the ORM level, with no `ON DELETE` in the migration, so deleting a Session requires the ORM and a fully loaded object graph. Risk RI-02 grows accordingly rather than shrinking.

Finally, storing Sessions does not by itself make per-user history possible. With `subject_id` unenforced and no identity behind it (ADR 0031), F-13 and F-48 remain out of reach until ADR 0009's authentication lands; what this decision buys for them is that the data will already be there when it does.
