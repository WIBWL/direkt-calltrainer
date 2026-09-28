// OIDC configuration. The issuer is build-time Vite env (repo-root .env) under
// the backend's own name, not a VITE_ copy, so the two cannot disagree —
// vite.config widens `envPrefix` for it. The client id is the same in every
// realm, so not a setting. Build-time is enough: one image per deploy.

// Required, deliberately without a default: every candidate value is wrong in
// some environment, and getting it wrong does not fail at build — the app just
// mints tokens the backend rejects, surfacing as a 401 far from the cause. Fail
// loudly instead.
const issuer = import.meta.env.OIDC_ISSUER;
if (!issuer) {
  throw new Error(
    "OIDC_ISSUER is not set. Add it to .env (e.g. http://localhost:18081/realms/direkt) and rebuild.",
  );
}

/** The realm issuer URL; the OIDC `authority`. Must match the backend's `iss` check. */
export const oidcAuthority: string = issuer;

/** The public Keycloak client that performs the login (see keycloak/direkt-realm.json). */
export const oidcClientId = "direkt-calltrainer";

/**
 * Where Keycloak sends the user back: always the SPA origin, so the realm needs
 * one redirect URI. Returning to the requested page is the app's job
 * (`onSigninCallback` in main.tsx).
 */
export const oidcRedirectUri: string =
  typeof window === "undefined" ? "" : window.location.origin + "/";
