# ADR 0060: Tenant Model and Company Sharing for Authored Scenarios

## Context

A new hire at a pilot company should see the Scenarios colleagues wrote (R-58). There is one realm, one deployment and one database, so tenancy is modelled inside the application.

## Decision

- Authored rows carry `tenant_id` (NULL for built-ins), set even on private rows, so sharing is a single `visibility` flip between `private` and `tenant`. A CHECK requires `tenant_id` for `tenant` visibility. `public` cannot be set by Users.
- Visibility is enforced server-side: public ∪ (tenant AND same tenant) ∪ own. The client never sends a tenant. Tests prove both directions.
- **The tenant is the alias of the caller's one Keycloak Organization**, from the `organization` claim (a default client scope). No claim, several aliases, or an over-long alias resolves to `default`. Several aliases are never resolved by picking one, because a wrong company would read another's Scenarios.
- A company's `tenant` row is created on first login, named after its alias. Only `default` is seeded. Tenants are never deleted.
- `GET /api/tenant` gives the client the display name (`null` for `default`).

## Consequences

R-58 is met without an identity subsystem; Keycloak is the one place a company is set up. Renaming an Organization's alias splits the company in two, so aliases are chosen once. Membership is the security boundary and must be admin-managed.
