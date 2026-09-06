# ADR 0053: Deterministic Constraint Names and Database-Enforced Vocabularies

## Status

Accepted

## Context

Two weaknesses in the schema surfaced while building the Session write and read paths, both of the same kind: the database was not enforcing or naming things that the code already assumed.

First, `Base.metadata` carried no naming convention. Left to itself, SQLAlchemy hands unnamed constraints to Postgres, which invents a name. Autogenerate (ADR 0027) then emits `op.create_unique_constraint(None, ...)` and `op.create_foreign_key(None, ...)`, whose mirrored `op.drop_constraint(None, ...)` in `downgrade()` cannot run at all. This produced a broken downgrade in three separate revisions in a row, each caught only because a human read the generated file — the practice CLAUDE.md prescribes precisely because of this failure mode. Relying on that reading is relying on vigilance where a configuration would do.

Second, several columns hold a closed vocabulary that only the application knew about: `session.status` is `completed` or `aborted` (ADR 0034), `analysis_job.kind` and `analysis_job.status` likewise (ADR 0032). All were plain `String` columns. A typo in a writer would be stored happily and only surface later as a Session that no query matches.

## Decision

`Base.metadata` is created with the naming convention SQLAlchemy and Alembic both document, covering indexes, unique constraints, checks, foreign keys and primary keys. Every constraint therefore gets a name derived from its table and columns, and autogenerate emits that name by itself. A test asserts that no constraint in a freshly migrated database escapes the convention.

Closed vocabularies are enforced by `CHECK` constraints rather than Postgres `ENUM` types. An ENUM is stricter but changing one requires `ALTER TYPE`, which cannot run inside a transaction and therefore cannot be part of an ordinary migration; swapping a CHECK is a single statement that can. The allowed values live as constants in `models.py` next to the constraint that enforces them, so the application and the database read from the same list. Simple range invariants — a Turn's `seq_index` starts at 0, durations are never negative — are expressed the same way.

## Consequences

The class of broken downgrade that appeared three times cannot recur: there is no longer an unnamed constraint for autogenerate to mishandle, and a test fails if one appears. Constraint names also become self-describing, so a foreign-key violation in a log names the table and column it concerns.

Introducing a convention retroactively is not free, and the migration that does it is more intricate than it looks: because Alembic applies the convention when *replaying* older revisions, a database created after this change gets different constraint names from one migrated before it. The rename does not resolve that ambiguity. It writes out the names it expects to drop, and those are the ones a *replayed* chain produces: a database created before the convention landed carries Postgres' own `<table>_<column>_fkey` names instead, and the revision would stop on the first constraint it cannot find. The tests cannot surface this, because they always replay the chain from empty, which is the case that works. No such database is known to exist. It is recorded here rather than repaired in place: the revision has already run everywhere it had to, and editing an applied migration would only make the code disagree with the history it produced. What the revision does handle is the other half — it restores the handful of names that earlier revisions chose by hand, so the chain runs in both directions. That subtlety is a one-time cost of adopting the convention late; a project that sets it up front never meets it.

The CHECK constraints make invalid writes fail loudly at the boundary instead of silently entering the store. The trade is that adding a status value now needs a migration rather than only a code change — which is the point: the vocabulary is part of the schema, and a reader of the schema can see it.
