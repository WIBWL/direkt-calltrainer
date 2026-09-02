# Research: cross-tenant (user-authored) scenarios

**Date:** 2026-09-02 · **Status:** research / options, not a decision
**Context:** F-59 / R-58, ADR 0024. In parallel, the feature that lets users
author their own scenarios is being built on `personas_scenarios_alex`.
**Question:** Where are user-authored scenarios stored — with the user or with
the company? How are they shared with colleagues?

---

## 1. What the feature asks for

> **R-58** — User-authored scenarios should be stored not just per-session but
> **per-tenant** (*mandantenbezogen*), so that colleagues can train with them
> without re-entering them. *(Source: SO-S 5)*
>
> **F-59** — Tenant-scoped scenario library. Priority **COULD**.

Core requirement: the storage owner is the **tenant**, not the individual person.
A new hire at Solox should immediately see the scenarios Solox created, without
anyone actively handing them over.

ADR 0024 deliberately left storage open ("free-text Scenario and Persona input
will need storage of its own in the Session schema, not yet designed") and
flagged two open questions:

- Do user-authored personas/scenarios appear in the same card-based library
  (ADR 0015), or in a separate "my …" space?
- Does user-supplied text need moderation/validation before it is used as
  system-prompt content? (Prompt-injection surface.)

---

## 2. Current state of the system (what exists today)

| Building block | State | Consequence for this feature |
|---|---|---|
| **Keycloak realm** | **One** shared realm `direkt` for all DiReKT services **and** both pilot companies (Solox, APPOLLO). Not a realm per company. | A "tenant" must be modelled *inside* one realm, not by realm separation. |
| **Deployment** | **One** instance on the university server (ADR 0020). Not a deployment per company. | Tenant separation happens in application logic + data, not through separate instances/DBs. |
| **Tenant entity** | Exists **nowhere** — not in the schema, the code, or Keycloak. | Has to be introduced. This is the real first decision, not the sharing. |
| **User entity** | No `user`/`account` table. `session.subject_id` = Keycloak `sub`, pseudonymous, **no** foreign key (ADR 0031). | "Store with the user" today means: a `created_by` column holding the `sub` string, with no referential integrity. |
| **`scenario` table** | Fully **global**. `/api/scenarios` serves every row to everyone, filtered only by `active`. `key` is unique (hand-authored slug). The DB is the source of truth (ADR 0041). | Needs visibility/ownership columns and a tenant-aware query. The hand slug does not fit user rows. |
| **Client IDs** | `session.extern_id` is an unguessable UUID (ADR 0050); the PK stays internal. | Reuse the same pattern for scenario IDs — never expose sequential ids or row counts. |
| **Keycloak version** | `quay.io/keycloak/keycloak:26.7` | The **Organizations** feature (native multi-tenancy within one realm) is available. |

---

## 3. Keep the three axes separate

Asking whether to store "with the user **or** with the company" is a false
either/or. A scenario has **three independent properties**:

| Axis | Column | Meaning | Example |
|---|---|---|---|
| **Authorship** | `created_by` (Keycloak `sub`) | Who wrote it? Drives edit rights, the "my scenarios" filter, attribution. | `alice` |
| **Ownership** | `tenant_id` (FK, nullable) | Which tenant does it belong to? `NULL` = built-in / global scenario. | `solox` |
| **Visibility** | `visibility` (enum) | Who may see it in their library? | `tenant` |

That answers the original question: **both**. A scenario is written by a *user*,
belongs to their *tenant*, and is private / tenant-wide / public depending on its
*visibility*. R-58 ("per-tenant") = ownership sits with the tenant, visibility is
at least `tenant`.

---

## 4. Layer 1 — where does tenant membership come from?

### Option A — Keycloak Organizations (native multi-tenancy)

Keycloak 26 provides **Organizations**: multiple tenants *inside* one realm, each
with its own members, invitation flows, and optionally its own identity provider.

- One Organization per company in the `direkt` realm (`solox`, `appollo`).
- Assign the optional `organization` client scope to `calltrainer-frontend`; the
  access token then carries an `organization` claim, shaped
  `"organization": { "solox": {} }` (alias → attributes).
- The backend reads the organization from the JWT — **exactly the way it reads
  `sub` today** ([backend/auth.py](../../backend/auth.py)). No member management
  in Calltrainer, invitations included.

**Pro**

- Identity stays in the IdP, where it belongs — consistent with ADR 0009 ("mirror
  direkt-dataplatform"). If the data platform adopts it too, both share the same
  tenant structure.
- No onboarding / invitation / admin UI to build in Calltrainer.
- A user can belong to multiple Organizations (e.g. external consultants).

**Con**

- The feature has to be enabled and configured in the **shared** realm `direkt`
  → coordination with the realm owner (data-platform team / university).
- `organization` is a relatively young feature; check its maturity.
- Users with no Organization (the dev users alice/bob/carol) need a defined
  fallback.

### Option B — derive the tenant from the email domain

`alice@solox.de` → tenant `solox`. A config map from domain to `tenant`.

**Pro** — No Keycloak change. Uses the `email` claim that is already in the
token. Implementable in an hour.

**Con** — Fragile: Gmail users, freelancers on a foreign domain, domain changes,
multiple domains per company. Every new company needs an entry. A shared realm
does not necessarily guarantee verified emails. The dev users are on
`@example.test` addresses.

### Option C — tenant and membership tables in Calltrainer

`tenant` + `tenant_membership(tenant_id, subject_id, role)`. Assignment by an
admin, or "first user creates the tenant + invites".

**Pro** — Full control, no dependency on realm changes, roles (author, admin)
freely modelled.

**Con** — Calltrainer becomes an identity-adjacent system: invitation flow,
admin UI, "which tenant am I in?" onboarding. Duplicates exactly what
Organizations does natively. `subject_id` has no FK yet (ADR 0031), so the
membership rows float without integrity too.

### Recommendation, layer 1

**Target: Option A (Keycloak Organizations).** As a bridge, a thin `tenant`
table in Calltrainer whose rows are seeded manually with Solox and APPOLLO, and
tenant resolution in this order:

1. `organization` claim in the token → `tenant.extern_ref`,
2. else email-domain map (Option B as fallback),
3. else a `default` tenant (dev users, individual users).

This keeps the door to Organizations open, does not block the in-flight
custom-scenario work, and initially needs **no** realm change.

---

## 5. Layer 2 — visibility / sharing model

The request was: **a library with public/private** rather than a redemption
code. That is the right direction. Expanded to three (or four) tiers:

### 5.1 Visibility enum

| Value | Who sees it | Role in the product |
|---|---|---|
| `private` | only `created_by` | Draft / personal scenario. **Default on creation.** |
| `tenant` | all members of `scenario.tenant_id` | **The core of R-58.** New colleagues get it automatically. |
| `public` | all users of all tenants | Built-in scenarios are effectively this (`tenant_id = NULL`, not editable). User promotion to `public` only after review (see §7). |

The library shows the **union** of what the caller may see:

```
visible(user) =
      visibility = 'public'
  ∪  (visibility = 'tenant'  AND tenant_id = tenant(user))
  ∪  (created_by = user.sub)
```

Each row gets a badge: **Built-in** / **Company** / **Mine**.
UI filters along the same three categories (this settles the open ADR 0024
question: one shared library **with** a "mine" filter, not a separate space).

### 5.2 The sharing action = one toggle

Create a scenario → `private`. A toggle **"Share with my company"** sets
`visibility = 'tenant'`. That is the **entire** sharing interaction for R-58 — no
codes, no recipient list, no redemption. A new colleague sees it on their next
login.

### 5.3 Redemption code — reframe, don't discard

A code/link is **not** a replacement for the library, it is a transport for a
**fourth** case: hand one scenario to a **specific person**, possibly in another
tenant, without making it company-wide or public (like "share a document via
link"). Two semantics:

- **Copy:** redeeming clones the scenario into the recipient's library
  (`created_by` = recipient, new row). Diverging copies, no updates from the
  original. Simple, no cross-tenant references at query time.
- **Reference:** redeeming inserts a `scenario_grant(scenario_id, subject_id)`
  row. The recipient sees the original, the author's edits propagate, revocable.
  More complex.

**For R-58 ("colleagues"), `tenant` visibility is strictly better** than a code
(no manual redemption, new joiners covered automatically). The code is at most a
later secondary feature for "share across the company boundary" — drop it for the
first cut.

---

## 6. Layer 3 — the schema, concretely

### 6.1 One table or two?

Built-in and user-authored scenarios in **one** table:

- `/api/scenarios` stays **one** query. `get_scenario(key)` in the orchestrator
  ([backend/library.py](../../backend/library.py)) does not change. The
  `session.scenario_id` FK works identically whether built-in or custom — two
  tables would need a polymorphic FK.
- Cost: every catalogue query now filters by `visibility`/`tenant_id`.

→ **Recommendation: one table.**

### 6.2 Columns (extending the `scenario` table on `personas_scenarios_alex`)

```python
tenant_id:   Mapped[int | None] = mapped_column(
    ForeignKey("tenant.tenant_id"), index=True)          # NULL = built-in/global
created_by:  Mapped[str | None] = mapped_column(String(64), index=True)  # Keycloak sub; NULL for seeds
visibility:  Mapped[str]        = mapped_column(String(12))  # CHECK IN ('private','tenant','public')
extern_id:   Mapped[uuid.UUID]  = mapped_column(Uuid, unique=True, default=uuid.uuid4)  # ADR 0050
created_at:  Mapped[datetime]
updated_at:  Mapped[datetime]
```

- `active` stays (retire instead of delete — Sessions reference the row, same
  rule as today).
- Make `key` (the hand slug) nullable for user rows; `extern_id` is what the
  outside world uses.
- CHECK constraint for `visibility` (ADR 0053, no Postgres ENUM).
- Index `(tenant_id, visibility)` and `(created_by)`.
- Edit rights: `created_by` **or** a tenant-admin role. Built-in scenarios:
  nobody (or only DiReKT admins).

### 6.3 `tenant` table

```python
class Tenant(Base):
    __tablename__ = "tenant"
    tenant_id:  Mapped[int]  = mapped_column(primary_key=True)
    extern_ref: Mapped[str]  = mapped_column(String(64), unique=True)  # KC org alias or seed key 'solox'
    name:       Mapped[str]  = mapped_column(String(120))
```

### 6.4 Same for `persona`

ADR 0024 also covers user-authored **personas**. Design the same column set
(`tenant_id`, `created_by`, `visibility`, `extern_id`) **once** and apply it to
both tables — don't solve it twice separately.

---

## 7. Layer 4 — enforcement & security

- Scope **every** scenario read/write server-side in `library.py` by the
  resolved tenant + `sub`. **Never** accept a `tenant_id` from the client
  (pool model → leakage risk, see sources in §9).
- **Prompt injection** (ADR 0024 flag): user scenario text goes into the system
  prompt. Mitigations: keep user text in clearly delimited sections, never let
  it override the call frame
  ([orchestrator.py](../../backend/session/orchestrator.py)), a length cap, and a
  moderation/review step before `visibility` can be raised above `private`.
- **Deletion / GDPR** (F-49): a user's private scenarios are deleted with the
  account; `tenant` scenarios survive (they belong to the tenant), `created_by`
  possibly anonymised. Ties into ADR 0031 (a real FK for `subject_id`).
- `extern_id` for every externally visible scenario reference.

---

## 8. Layer 5 — phased plan (does not block the in-flight work)

| Phase | Content | Delivers |
|---|---|---|
| **0 — now** | Custom scenarios land as `visibility='private'`, `created_by=sub`, `tenant_id=NULL`. No sharing. Just: your own scenarios show up under "Mine". | ADR 0024 (scenario part), unblocks `personas_scenarios_alex` |
| **1** | `tenant` table, seeded with Solox + APPOLLO. Tenant resolution via email-domain map / manual assignment. "Share with company" toggle → `visibility='tenant'`. | **R-58 / F-59** |
| **2** | Switch tenant resolution to the Keycloak `organization` claim; `tenant.extern_ref` = org alias. The domain map becomes the fallback. | Clean identity, Keycloak invitation flows |
| **3 — optional** | `public` promotion with review; share links for cross-tenant one-offs. | Nice-to-have |

---

## 9. Recommendation summary

1. **Model three axes separately:** `created_by` (user), `tenant_id` (company),
   `visibility` (`private`/`tenant`/`public`). Not an either/or.
2. **A library with visibility tiers** as the primary mechanism — the instinct
   against redemption codes is correct. The code is at best a later secondary
   feature for "across the company boundary"; leave it out for now.
3. **Custom + built-in scenarios in one table**, `extern_id` to the outside.
4. **Tenant identity:** target Keycloak Organizations, bridged by a small
   `tenant` table + email-domain / manual resolution until Organizations is
   enabled in the `direkt` realm.
5. **Phases 0 → 1 → 2**, so the in-flight custom-scenario work does not wait:
   private only first, then tenant sharing, then Organizations.
6. Design the column set **once** and apply it to `scenario` **and** `persona`
   (ADR 0024 covers both).

Next step: an ADR "Tenant model and visibility for user-authored
scenarios/personas" (successor to / extension of ADR 0024, referencing ADR 0009,
0031, 0041, 0050).

---

## 10. Sources

- [Keycloak — Announcing the Organizations feature](https://www.keycloak.org/2024/06/announcement-keycloak-organizations) — claim shape `"organization": { "orga": {} }`, optional `organization` client scope, enable via `--features organization`
- [Exploring Keycloak 26: Introducing the Organization Feature for Multi-Tenancy](https://medium.com/keycloak/exploring-keycloak-26-introducing-the-organization-feature-for-multi-tenancy-fb5ebaaf8fe4)
- [Red Hat — Managing organizations (Keycloak 26 Server Administration Guide)](https://docs.redhat.com/en/documentation/red_hat_build_of_keycloak/26.0/html/server_administration_guide/managing_organizations)
- [Multitenancy in Keycloak Using the Organizations Feature (Skycloak)](https://skycloak.io/blog/multitenancy-in-keycloak-using-the-organizations-feature/)
- [WorkOS — The developer's guide to SaaS multi-tenant architecture](https://workos.com/blog/developers-guide-saas-multi-tenant-architecture) — `organization_id` on every table except `users`, scope all reads/writes
- [Bytebase — Multi-Tenant Database Architecture Patterns Explained](https://www.bytebase.com/blog/multi-tenant-database-architecture-patterns-explained/) — pool / bridge / silo
- [Clerk — How to Design a Multi-Tenant SaaS Architecture](https://clerk.com/blog/how-to-design-multitenant-saas-architecture)
- [GitHub Actions — workflow template visibility cascade](https://josh-ops.com/posts/github-dot-github-repository/) — public → all, internal → internal+private, private → private only; model for the `public`/`tenant`/`private` cascade
- Project ADRs: 0009 (Keycloak/OIDC), 0024 (user-authored scenarios/personas), 0031 (pseudonymous `subject_id`), 0041 (scenarios/personas from the DB), 0050 (unguessable IDs), 0053 (CHECK-enforced vocabularies)
