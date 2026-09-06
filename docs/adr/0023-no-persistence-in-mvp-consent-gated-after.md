# ADR 0023: No Session Data Persisted Beyond the MVP; Consent-Gated Storage After

## Status

Superseded by ADR 0034 (Session Data Is Persisted in the MVP, Written Once at Session End)

## Context

arc42 flags DSGVO implementation as an open risk (Kapitel 11, "Unklare Datenschutz-Umsetzung"): where Session data is processed and stored (EU hosting), how long it is retained, and whether user consent is captured. ADR 0010 provides a database for Session data, and ADR 0011 guarantees no data leaves the DiReKT gateway during STT/LLM/TTS processing, but neither addresses whether Session audio, transcripts, or Feedback are stored at all, for how long, or under what legal basis.

## Decision

We will not persist Session audio, transcripts, or Feedback beyond the Session itself for the MVP. Once a Session ends, this data exists only in the memory of the running Session/worker processes and is discarded; nothing is written to the database (ADR 0010) or any other durable store.

Beyond the MVP, we will persist Session data to the project's own PostgreSQL instance (ADR 0010) — running on the same university-hosted server as the DiReKT gateway (ADR 0011) and the application server (ADR 0020), keeping the entire pipeline's data residency inside the same DSGVO-compliant, university-hosted environment — but only for a User who has given consent. Consent is captured once, during account setup, and the User can change that preference at any time afterward. Users have full, direct control over their own stored data and can delete it themselves at any time via a simple self-service action, rather than by submitting a request that a human then has to action.

## Consequences

For the MVP, there is no retained-data DSGVO surface to manage at all, no retention period, deletion workflow, or access-control question, since nothing survives the Session. The tradeoff is that feedback aggregated across sessions and long-term progress tracking (F-13, F-48) are not yet possible: an user only ever sees the feedback for the session they just completed.

Once persistence is introduced, consent is the sole legal basis for storage — there is no separate "legitimate interest" path, so a User who never opts in simply never has Session data retained beyond the call itself, even under the post-MVP model. Self-service deletion requires a corresponding delete path across the persistence schema, which is not yet designed. Because the whole chain (application server, DiReKT gateway, database) stays within the university's own hosted infrastructure, this decision introduces no cross-border transfer question or third-party processor beyond what ADR 0010, ADR 0011, and ADR 0020 already established.
