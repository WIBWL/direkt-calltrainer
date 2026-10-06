# ADR 0063: Scenario Field Limits Served From One Source

## Context

The editor kept a hand-copied set of field caps that drifted from the backend's, so the form accepted input the save then rejected.

## Decision

The backend's `FIELD_LIMITS` is the only source. `GET /api/scenarios/field-limits` serves it under the wire's field names, and the editor uses it for every `maxLength`. A rough fallback in the frontend is used only if the request fails; the server still validates. The caps cover authorable Scenario fields only.

## Consequences

Tuning a cap is a one-line change in one place. The editor makes one extra request when it opens.
