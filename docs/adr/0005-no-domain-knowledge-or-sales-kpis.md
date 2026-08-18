# ADR 0005: No Automated Enterprise/CRM Integration, No Sales KPIs

## Status

Accepted

## Context

The tool could instead have been built to pull in domain knowledge automatically from the company's own systems (CRM, product databases) and to assess sales outcomes, similar to classic sales trainers. Stakeholder interviews and the feature specification (F-27, WON'T; F-28, WON'T) explicitly ruled both out. This does not rule out a user manually providing session-specific context: the feature specification separately plans an optional, user-driven document upload (F-26, SHOULD; F-45), which is a Session-scoped convenience, not an ambient enterprise knowledge base.

## Decision

We will not build any automated integration with enterprise/CRM systems or other company databases to feed the Persona domain knowledge, and we will not use sales KPIs (close rate, revenue) as success metrics anywhere in the product. Scope is limited to communication behavior — clarity, tone, structure — independent of automatically-sourced domain expertise or deal outcome. Optional, manually user-provided documents for a Session (F-26) are a separate, permitted feature and not affected by this decision.

## Consequences

Implementation stays simpler, since no enterprise-system ingestion pipeline is needed, and the product stays usable across both support and advisory contexts without per-customer integration setup. The tradeoff: experienced users may find conversations less realistic when automatically-sourced domain facts are missing, a risk already flagged in arc42 — mitigated only as far as a user chooses to upload their own context via F-26.
