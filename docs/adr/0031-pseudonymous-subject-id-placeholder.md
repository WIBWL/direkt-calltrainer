# ADR 0031: Pseudonymous subject_id Placeholder Instead of a User Foreign Key

## Status

Accepted. Its own revisit condition — ADR 0009's auth integration — has since been met; the decision stands, but on a different reason than the one below. See the Consequences.

## Context

ADR 0009 decided on Keycloak/OIDC for user authentication, but that integration is not yet built, and this schema has no persisted User/Account entity at all. Session persistence still needs to record whose Session a given row belongs to, both for ADR 0023's per-user consent and self-service-deletion model (carried forward by ADR 0034), and for eventual per-user Feedback aggregation (F-13, F-48).

## Decision

`Session.subject_id` is a plain `String` column, not a foreign key to any User table. It is documented in-line as a pseudonym placeholder for what will later be the Keycloak JWT `sub` claim.

## Consequences

The persistence schema (ADR 0026) doesn't need to wait on, or couple to, the Keycloak integration (ADR 0009) landing first, and can be built and migrated independently of it. The cost is that nothing today enforces that `subject_id` values are valid, unique per person, or even present — no referential integrity ties Sessions to actual identities yet. This is expected to be revisited, adding the real foreign key and constraint, once ADR 0009's auth integration exists.

ADR 0009 has since landed, and `subject_id` now holds the real Keycloak `sub`, handed from the handshake through to `persist_session` (`backend/auth.py`, `backend/session/persistence.py`). That settles the placeholder half of this decision but not the missing foreign key, which now rests on a different reason than the one above: identity lives in Keycloak, and there is no local User table for a foreign key to point at. Creating one solely to carry that constraint would duplicate the identity provider. The column stays a plain `String` deliberately rather than provisionally, and ADR 0052 leaves it unindexed on the same grounds.

What the pseudonym does not do is settle the data-protection question. The mapping from `sub` to a person is held by the Keycloak realm in the same Compose stack on the same server, so re-identification is one query away for anyone who can read the Session database: this is pseudonymisation as a mitigation, not anonymisation. The stored transcripts carry whatever the User said aloud, their name and their company included, so no choice of identifier would make the data anonymous either. Sessions are personal data, and the obligations that follow — a retention period and a deletion path (ADR 0034) — are open work, not discharged by how this column is designed. The third, an ownership check on the read route, is done: `subject_id` is compared against the caller's `sub`, which is what turns this column from a recorded value into an enforced one (ADR 0050).
