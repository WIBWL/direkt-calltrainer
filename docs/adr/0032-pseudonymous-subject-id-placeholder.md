# ADR 0032: Pseudonymous subject_id Placeholder Instead of a User Foreign Key

## Status

Proposed

## Context

ADR 0009 decided on Keycloak/OIDC for user authentication, but that integration is not yet built, and this schema has no persisted User/Account entity at all. Session persistence still needs to record whose Session a given row belongs to, both for ADR 0024's per-user consent and self-service-deletion model, and for eventual per-user Feedback aggregation (F-11, F-13).

## Decision

`Session.subject_id` is a plain `String` column, not a foreign key to any User table. It is documented in-line as a pseudonym placeholder for what will later be the Keycloak JWT `sub` claim.

## Consequences

The persistence schema (ADR 0027) doesn't need to wait on, or couple to, the Keycloak integration (ADR 0009) landing first, and can be built and migrated independently of it. The cost is that nothing today enforces that `subject_id` values are valid, unique per person, or even present — no referential integrity ties Sessions to actual identities yet. This is expected to be revisited, adding the real foreign key and constraint, once ADR 0009's auth integration exists.
