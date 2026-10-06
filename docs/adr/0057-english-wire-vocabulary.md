# ADR 0057: English Wire Vocabulary

## Context

The schema was English (ADR 0026) but the JSON on the wire was German, which needed translation maps in several modules and two names for everything.

## Decision

The wire matches the schema everywhere, including the Scenario library: field names, enum values, route paths, metric keys and the wrap-up's JSON contract. The client sees `extern_id`, never a key. German stays only in user-facing content: display names, labels, prose and seed content. The glossary term is used for identifiers, for example `/api/tenant`, not `/api/company`.

## Consequences

There is one vocabulary, and `protocol.ts` mirrors the Python models.
