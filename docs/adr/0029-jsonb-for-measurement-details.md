# ADR 0029: JSONB for Flexible Per-Measurement Detail Data

## Status

Accepted

## Context

`Messung` (a measurement of a `MetrikTyp` within a `Turn` — e.g. tempo, intonation) stores one numeric value (`wert`) per row. The underlying speech analysis can also produce a variable-shaped detail payload alongside that value — for example a time series of how a metric evolved across the turn — which differs per metric type and isn't known in advance as a fixed set of columns.

## Decision

We added `Messung.detail_json` as a nullable `JSONB` column, using `sqlalchemy.dialects.postgresql.JSONB` specifically, rather than a portable/dialect-neutral JSON type or a separate table per metric-type detail shape.

## Consequences

This gives schema-less storage for whatever a given analysis metric wants to attach to a measurement, without requiring a migration each time a new metric type ships a different detail shape, and Postgres can still index or query into `JSONB` fields later if needed. In exchange, this column is Postgres-specific — consistent with ADR 0010, where Postgres is a project-owned choice rather than something requiring database portability — but it does mean the schema can no longer be trivially ported to another SQL dialect.
