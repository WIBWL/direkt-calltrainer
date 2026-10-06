# ADR 0053: Deterministic Constraint Names and Database-Enforced Vocabularies

## Context

Unnamed constraints made autogenerate emit `drop_constraint(None, …)` downgrades that cannot run. Closed vocabularies existed only in the code.

## Decision

- `Base.metadata` carries the standard naming convention, so every constraint gets a derived name. A test asserts that none escapes it. Never name a constraint by hand.
- Closed vocabularies and simple range invariants are `CHECK` constraints, not `ENUM`s, so that changing one is an ordinary transactional migration. The allowed values are constants beside the constraint.
- `op.create_check_constraint` and `op.drop_constraint` apply the convention themselves, so a migration passes the bare name.

## Consequences

Broken downgrades of this kind cannot recur, and constraint names are self-describing. A new status value needs a migration, which is intended.
