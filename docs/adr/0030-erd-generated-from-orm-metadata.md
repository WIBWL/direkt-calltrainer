# ADR 0030: ER Diagram Generated from ORM Metadata

## Context

A hand-drawn ER diagram drifts from `models.py`.

## Decision

A script draws the diagram from the models' metadata, against an empty in-memory SQLite engine, on demand. The output is gitignored and not part of the docs site.

## Consequences

The diagram is always current when drawn, and no stale copy is committed. Drawing it needs Graphviz.
