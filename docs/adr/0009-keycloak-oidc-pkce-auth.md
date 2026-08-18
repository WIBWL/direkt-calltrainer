# ADR 0009: Authentication via Keycloak (OIDC Authorization Code Flow + PKCE)

## Status

Accepted

## Context

Users need to be authenticated before performing Sessions, and their identity needs to travel with requests to the external Data Platform. Keycloak is the project's designated identity provider.

## Decision

We will authenticate users via the OIDC Authorization Code Flow with PKCE, with Keycloak as the identity provider. The frontend performs the login redirect directly against Keycloak, not proxied through the backend, and receives a JWT that the backend later forwards when calling the Data Platform.

## Consequences

This is the standard, secure flow for a public SPA client — no client secret to protect, and safe against authorization code interception. It requires the frontend to hold and refresh a JWT, and the backend to validate and forward it correctly. Implementation is pending real Keycloak realm/client configuration (`KEYCLOAK_URL` is still a placeholder).
