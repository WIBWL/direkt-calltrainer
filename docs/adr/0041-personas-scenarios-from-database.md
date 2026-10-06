# ADR 0041: Personas and Scenarios Loaded from the Database

## Context

The library is meant to grow (ADR 0002), without a deployment for each change.

## Decision

The `persona` and `scenario` tables are the source of truth. The setup API serves them, and the orchestrator loads the selected pair at call start and builds the system prompt from them plus the fixed prompt frame. Seed content lives in code and is upserted at boot. The live call depends on plain value types, never on database access.

## Consequences

Content changes need no deployment. A call cannot start without the database, and running locally requires a migrated, seeded database.
