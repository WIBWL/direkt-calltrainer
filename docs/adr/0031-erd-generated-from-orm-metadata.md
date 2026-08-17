# ADR 0031: ER Diagram Generated from ORM Metadata

## Status

Proposed

## Context

With the schema now defined in code (ADR 0027), the project's documentation needs an ER diagram (feeding arc42's Bausteinsicht/data model). A hand-drawn diagram risks drifting from the actual schema as `models.py` evolves.

## Decision

`scripts/generate_erd.py` generates the ER diagram directly from `Base.metadata` using `sqlalchemy-schemadisplay` and `pydot`/Graphviz, against an empty in-memory SQLite engine so no running database is required. It writes both `docs/er_modell.png` and `docs/er_modell.svg`, styled to match the project's existing design tokens (Blue-Ramp palette, IBM Plex Mono font). The generated files are committed to the repository rather than produced at docs-build time.

## Consequences

The diagram cannot diverge from the real schema as long as it is regenerated after a `models.py` change, but that regeneration is a manual step (`python scripts/generate_erd.py`) with local-only prerequisites (the Graphviz `dot` binary, optionally the IBM Plex Mono font) and is not run in CI. The "stays in sync" guarantee therefore still depends on a developer remembering to re-run the script and commit the updated files after a schema change.
