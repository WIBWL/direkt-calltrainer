# ADR 0060: Tenant Model and Company Sharing for Authored Scenarios

## Status

Accepted and implemented through phase 1. **Builds on ADR 0058** (User-Authored
Scenarios): that decision established the row shape (`created_by`, `extern_id`,
`visibility`), the one-table model and the owner-scoped CRUD. This ADR adds the
third axis — **ownership by a company** — and the sharing that R-58 / F-59
(*mandantenbezogene Szenario-Bibliothek*, COULD) asks for: a new hire at a pilot
company should see the Scenarios their colleagues wrote without anyone handing
them over. Works within ADR 0031 (pseudonymous `subject_id`). Backed by
`docs/research/cross-tenant-scenarios.md`.

A caller's company comes from a **`tenant` claim** — a Keycloak user attribute
an admin sets when creating the account. That is the mechanism and it works
today; Keycloak Organizations (phase 2) is an optional richer source for the
same claim, not a prerequisite. Phase 3 (`public` promotion with review,
cross-tenant share links) is untouched.

## Context

After ADR 0058 an authored Scenario has two independent properties: **authorship**
(`created_by`, drives edit rights and the "Mine" filter) and **visibility**
(`private` or `public`). R-58 needs a third: **ownership** — which company the
Scenario belongs to — so that "share it" means "share it with my colleagues",
not "make it public to every tenant".

There is one shared Keycloak realm (`direkt`) for both pilot companies, one
deployment (ADR 0020), one database. So a tenant has to be modelled *inside* the
application, not by realm or deployment separation.

## Decision

### `tenant_id`, and a `visibility` of `tenant`

`scenario` (and `persona`, for symmetry) gains `tenant_id` — a nullable foreign
key to a new `tenant` table. It is set on **every** authored row, even a private
one, so sharing is a pure `visibility` flip. `NULL` = a shipped built-in.

`visibility` widens to `('private','tenant','public')`, with a second CHECK that
`visibility = 'tenant'` requires `tenant_id IS NOT NULL`. `public` is still not
a value a User can set on their own row — that needs review (phase 3).

Because `'tenant'` is meaningless before the `tenant` column exists, this lands
as a **second** `visibility` CHECK migration (ADR 0058's was the first). Two
migrations rather than one is the accepted price of not blocking F-34 on
tenancy.

### Visibility is enforced server-side, never trusted from the client

`backend/library.py` scopes every read by the caller's resolved tenant and
`sub`:

```
visible(caller) =
      visibility = 'public'
  ∪  (visibility = 'tenant'  AND tenant_id = tenant(caller))
  ∪  (created_by = caller.sub)
```

The client never sends a `tenant_id`. A bug here is a cross-tenant data leak, so
`tests/` proves the query in both directions — a caller sees their tenant's
shared rows, and does **not** see another tenant's.

### Sharing is one toggle

A single **"Share with my company"** toggle flips `visibility` between `private`
and `tenant` (`PUT /api/scenarios/{id}/sichtbarkeit`, author only). That is the
entire sharing interaction for R-58 — no redemption codes, no recipient lists,
no invitations. A colleague sees it on their next load. Cross-tenant share links
stay a phase-3 possibility.

The setup screen shows four Scenario filters — **Alle / Standard / Eigene /
`<company name>`** — and badges each card. `GET /api/unternehmen` gives the
client the resolved company name (`null` for the `default` tenant, which hides
the company chip); the name is never something the client sends.

### Tenant identity comes from Keycloak, resolved per request

A `tenant` table (`tenant_id` PK, `extern_ref` unique, `name`), seeded with the
two pilot companies plus a `default` tenant. `backend/tenants.py` resolves a
request's tenant to an `extern_ref` in this order:

1. **the `tenant` claim** — a custom Keycloak user attribute, set by whoever
   creates the account (accounts are created by hand anyway, ADR 0009) and
   mapped into the access token by the `calltrainer tenant` protocol mapper.
   It matches `tenant.extern_ref` directly.
2. else the **`default`** tenant.

An unknown ref (a typo'd attribute) resolves to `default`, not an error. The backend reads the claim exactly as it reads `sub`; there is
**no** tenant/membership/invitation management inside Calltrainer (ADR 0009
keeps identity in the IdP). Keycloak Organizations, if the shared realm adopts
it, is just another way to populate the same `tenant` claim — an org→claim
mapper — and needs no code change here.

### Phased

| Phase | Scope | Delivers |
|---|---|---|
| **0** (ADR 0058) | authoring, `visibility in ('private','public')`, addressing by `extern_id` | F-34, F-58 |
| **1** | `tenant` table + seed; `tenant_id`; `visibility` widened to `'tenant'`; `tenant`-claim → `default` resolution; the share toggle | R-58 / F-59 |
| **2 — optional** | Keycloak Organizations as an alternative source for the `tenant` claim | Cleaner IdP-managed membership |
| **3 — optional** | `public` promotion behind review; cross-tenant share links | Nice-to-have |

## Consequences

R-58 is met without Calltrainer growing an identity subsystem: the backend reads
a tenant from the JWT the way it already reads `sub`, and "sharing" is a boolean.

The visibility filter sits on the hot path for `/api/scenarios` and every
`get_scenario` in the Session pipeline; an index on `(tenant_id, visibility)`
and on `created_by` covers it.

Deletion (F-49): a User's `private` Scenarios go with their account; `tenant`
rows survive because they belong to the tenant, with `created_by` anonymised.
This wants the real `subject_id` foreign key ADR 0031 deferred — noted, not
introduced.

`CONTEXT.md` gains a **Tenant** term. The migrations and the ER diagram
regenerate from `backend/db/models.py` as usual.
