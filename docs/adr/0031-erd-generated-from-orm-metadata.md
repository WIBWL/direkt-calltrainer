# ADR 0031: ER Diagram Generated from ORM Metadata

## Status

Accepted

## Context

With the schema now defined in code (ADR 0027), the project's documentation needs an ER diagram (feeding arc42's Bausteinsicht/data model). A hand-drawn diagram risks drifting from the actual schema as `models.py` evolves.

## Decision

`scripts/generate_erd.py` generates the ER diagram directly from `Base.metadata` using `sqlalchemy-schemadisplay` and `pydot`/Graphviz, against an empty in-memory SQLite engine so no running database is required. It writes both `docs/er_modell.png` and `docs/er_modell.svg`, styled to match the project's existing design tokens (Blue-Ramp palette, IBM Plex Mono font). The generated files stay committed to the repository, and a MkDocs `on_pre_build` hook (`scripts/mkdocs_hooks.py`) additionally re-runs the generator before every docs build, so the diagram published on `docs/datenmodell.md` is derived from the current `models.py` rather than from whatever was last committed. When the generator cannot run — typically because the Graphviz `dot` binary is absent — the hook logs a warning and the build continues with the committed diagram instead of failing.

## Consequences

The published diagram cannot diverge from the real schema: anyone building or serving the docs gets one rendered from the models in front of them. Because the files also remain committed, they stay available to readers who never build the docs — for instance directly on the Git forge — and that committed copy is what a build without Graphviz falls back to. The cost is that the docs build now depends on the schema being importable: a `models.py` that raises on import degrades the diagram to the committed version rather than surfacing the error loudly, so an import-level breakage shows up only as a warning in the build log.

The committed files can still fall behind between builds, since nothing forces a developer to run the generator before committing a `models.py` change. What the hook removes is the risk of the *published* diagram being stale, not the risk of a stale file in a diff.
