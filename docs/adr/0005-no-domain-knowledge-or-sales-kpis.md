# ADR 0005: No Automated Enterprise/CRM Integration, No Sales KPIs

## Context

The tool could pull domain knowledge from company systems and judge sales outcomes. The requirements (C-05, R-45, R-46) rule both out.

## Decision

There is no automated integration with CRM or other company systems, and no sales KPI (close rate, revenue) is used anywhere. Scope is communication behaviour. A document uploaded by the User for a Scenario (F-26) is permitted.

## Consequences

There is no ingestion pipeline and no per-customer setup. Conversations may feel less realistic to experts unless they upload their own context.
