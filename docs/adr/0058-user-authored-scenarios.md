# ADR 0058: User-Authored Scenarios

## Context

Users want to train on their own situations (F-34) and from their own documents (F-58). Personas stay curated, because each has a fixed voice and language.

## Decision

- Authored and built-in Scenarios share the `scenario` table. `created_by` (Keycloak `sub`, no foreign key) is NULL for a built-in. Rows are addressed by `extern_id`, and `visibility` is `private`, `tenant` or `public`.
- CRUD lives under `/api/scenarios`, scoped server-side by the verified `sub`. Only the author may edit. Delete is soft (`active = False`), because past Sessions reference the row. A foreign or invisible row answers 404.
- The situation (`description`) is required. Case fields may be blank, meaning "improvise".
- `POST /api/scenarios/document` turns a text-layer PDF into a fact list for the case-facts field (ADR 0059). The file is never stored.
- `persona` carries the same authored-content columns for symmetry, but nothing writes them.

## Consequences

`library.py` is the one place that reads and writes the reference tables, and every catalogue query filters by author and tenant.
