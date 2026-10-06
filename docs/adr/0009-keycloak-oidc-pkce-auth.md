# ADR 0009: Authentication via Keycloak (OIDC Authorization Code Flow + PKCE)

## Context

Users must be authenticated, and Keycloak is the project's identity provider.

## Decision

- The SPA logs in with the OIDC authorization code flow and PKCE, as the public client `calltrainer-frontend` in the `direkt` realm, directly against Keycloak.
- The backend verifies the RS256 access token against the realm's JWKS and checks `iss` and the audience `calltrainer-backend`.
- A token failure is a 401. A JWKS or infrastructure failure is a 5xx, so an outage is not masked as a login problem.
- A browser cannot set headers on a WebSocket, so the token rides in the `session.start` handshake message. An invalid token closes the socket with 1008.
- The issuer is the single setting `OIDC_ISSUER`, read by the backend and served to the SPA. The client id and audience are constants.
- Access needs a client role (ADR 0109).

## Consequences

This is the standard secure flow for a public SPA, with no client secret. The SPA must hold and refresh the token. The local realm import (`keycloak/direkt-realm.json`) is the template for the real realm.
