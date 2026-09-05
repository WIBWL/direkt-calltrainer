# ADR 0009: Authentication via Keycloak (OIDC Authorization Code Flow + PKCE)

## Status

Accepted — implemented (see *Implementation*, added after the fact)

## Context

Users need to be authenticated before performing Sessions, and their identity needs to travel with requests to the external Data Platform. Keycloak is the project's designated identity provider.

## Decision

We will authenticate users via the OIDC Authorization Code Flow with PKCE, with Keycloak as the identity provider. The frontend performs the login redirect directly against Keycloak, not proxied through the backend, and receives a JWT that the backend later forwards when calling the Data Platform.

## Consequences

This is the standard, secure flow for a public SPA client — no client secret to protect, and safe against authorization code interception. It requires the frontend to hold and refresh a JWT, and the backend to validate and forward it correctly.

## Implementation

Built for this stack (FastAPI) and its WebSocket data path.

**Realm and client.** Realm `direkt`, reused from the data platform (one realm, many services — switching between dev and prod changes only the host in `OIDC_ISSUER`). A new public client `calltrainer-frontend` (`publicClient`, PKCE S256, standard flow) performs the login. A pinned audience mapper adds `calltrainer` to the access token; the backend requires that audience. `keycloak/direkt-realm.json` is the **dev-only** import (users `alice`/`bob`/`carol`, password = username); production needs the client and mapper added by hand.

**Frontend** (`frontend/src/{oidcConfig,auth,api,AuthGate}.ts[x]`). `oidc-client-ts` + `react-oidc-context`. One `UserManager` is the source of truth for the token; `api.ts` and `useSessionSocket.ts` read it live at request time so a silent renew is picked up without a re-render. `AuthGate` wraps the app: splash while the session restores, a login button (`signinRedirect`) otherwise, `<App/>` once authenticated. No router — `react-oidc-context` consumes the `?code=&state=` on mount. OIDC config is build-time Vite env (`VITE_OIDC_ISSUER`), consistent with `VITE_API_URL`.

**Backend** (`backend/auth.py`). `PyJWT[crypto]` verifies the RS256 signature against the realm JWKS (resolved from the OIDC discovery document, or `OIDC_JWKS_URL` when the backend reaches Keycloak under a different host than the browser — the compose case). It checks `iss` and `aud`, and surfaces `sub` plus `resource_access.calltrainer.roles`. A token-level failure is a 401 (the client's problem); a JWKS/infra failure propagates as a 5xx (not the client's problem — masking it as a 401 would hide the outage). `require_user` is a FastAPI dependency on `/api/personas` and `/api/scenarios`; `/health` and the static SPA mount stay open. **No role check** — any valid realm token may use the app (there is no admin surface); `roles` is carried so a check can be added later without reshaping this.

**The WebSocket.** A browser cannot set an `Authorization` header on a `WebSocket`, so the token rides inside the `session.start` handshake message (`backend/api/session_ws.py::_handshake`), which the protocol already sends first. A missing or invalid token closes the socket with 1008 (policy violation). The verified `sub` is threaded into `SessionOrchestrator` so it is on hand when ADR 0034's persist-at-session-end path lands (it becomes `session.subject_id`, ADR 0031).

**Local dev.** `compose.yaml` runs its own Keycloak (`start-dev --import-realm`, host port 18081, `KC_HOSTNAME` fixing the issuer). `KC_HOSTNAME`/`--hostname-strict=false` plus `OIDC_JWKS_URL` resolve the browser-vs-container host mismatch.

**Out of scope, deliberately:** forwarding the JWT onward to the Data Platform (no such call exists yet); F-49's data-protection notice and the consent gate ADR 0034 ties to an identified user.
