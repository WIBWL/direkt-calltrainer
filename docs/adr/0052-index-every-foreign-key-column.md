# ADR 0052: Index Every Foreign-Key Column

## Status

Accepted (supersedes ADR 0028)

## Context

ADR 0028 declared no secondary indexes beyond primary keys, foreign keys and the natural-key uniqueness constraints, on the explicit grounds that no code queried the schema yet and any index would be a guess. It named the condition for revisiting itself: "once the read side (Session history, aggregated Feedback, F-13/F-48) is built against real query patterns rather than guesses."

That condition is now met. Sessions are written at the end of a call (ADR 0034) and read back individually through `GET /api/sessions/{extern_id}`, which loads a Session's Turns by `turn.session_id`. ADR 0034 further promises Users self-service deletion of their own data, and the delete path walks the whole Session subtree.

What ADR 0028 did not weigh is that an unindexed foreign key costs more than a slow lookup. Postgres indexes the referenced primary key but never the referencing column, so every delete of a parent row scans each child table sequentially to check for references. The promised deletion therefore degrades with table size even though nobody ever queries the child tables directly.

## Decision

Every foreign-key column in the schema carries an index, declared on the model with `index=True` and therefore present in the migrations and the ER diagram like any other part of the schema. This is the default Django and Rails apply, and it is a rule that holds without per-column judgement: a reviewer can check it mechanically, and a test does (`test_every_foreign_key_column_is_indexed`).

We index all of them rather than only the ones on a known path. A selective rule would need re-deciding at every new query, and the columns it would exclude — the lookup-table references — cost almost nothing to index at this cardinality.

Indexes that are *not* foreign keys remain out of scope, and ADR 0028's reasoning still governs them: `session.subject_id` in particular stays unindexed until authentication (ADR 0009) makes per-user history possible at all.

## Consequences

Deleting a Session no longer scans its child tables, and reading one back uses an index instead of a sequential scan — both matter more as stored Sessions accumulate, which is exactly what ADR 0034 set up. The rule is uniform, so new tables inherit it without a fresh discussion, and its violation is caught by a test rather than by review.

The cost is fourteen additional indexes to keep updated on write and to store. At this volume that is negligible, and the write path is a single insert per Session at the end of a call, not a hot loop. Should a table ever become write-heavy, an individual index can be dropped — but that would be a deliberate exception to a stated rule rather than the absence of one.
