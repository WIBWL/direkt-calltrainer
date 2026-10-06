# ADR 0031: Pseudonymous subject_id Instead of a User Foreign Key

## Context

Stored Sessions must record whose they are. Identity lives in Keycloak, and there is no local User table.

## Decision

`session.subject_id` is a plain, indexed string holding the Keycloak `sub`, with no foreign key. Ownership is enforced by comparing it with the caller's `sub` (ADR 0050).

## Consequences

The identity provider is not duplicated. This is pseudonymisation, not anonymisation: the realm maps `sub` to a person, and transcripts contain whatever the User said. Sessions are personal data, governed by ADR 0066/0067.
