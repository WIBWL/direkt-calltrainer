# ADR 0029: JSONB for Flexible Per-Measurement Detail Data

## Context

A Measurement has one numeric value, but each metric also produces a detail payload of its own shape: curves, counts and located events.

## Decision

`Measurement.detail_json` is a nullable Postgres `JSONB` column.

## Consequences

A new metric's detail needs no migration. The schema is Postgres-specific, which is acceptable under ADR 0010.
