# ADR 0052: Index Every Foreign-Key Column

## Context

Postgres never indexes the referencing side of a foreign key, so every parent delete scans the child tables.

## Decision

- Every foreign-key column carries `index=True`, enforced by a test.
- Where a unique constraint already leads with the foreign-key column, the extra index is left off. The test accepts either, so this one is on the reviewer.
- Other indexes need a named read path, recorded at the column: `session.subject_id`, `consent.subject_id`, and `created_by` on authored content.

## Consequences

Deletes and reads stay fast as data grows, and new tables inherit the rule without discussion. The write cost is negligible at one insert per call.
