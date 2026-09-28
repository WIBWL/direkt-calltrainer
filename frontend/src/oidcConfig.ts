// OIDC configuration. The issuer comes at runtime from the frontend
// container's OIDC_ISSUER (served as /config.js by spa.conf.template), the backend's
// own name, so one image serves every realm. The client id is the same in
// every realm, so not a setting.

// Required, deliberately without a default: every candidate value is wrong in
// some environment, and getting it wrong does not fail at build — the app just
// mints tokens the backend rejects, surfacing as a 401 far from the cause. Fail
// loudly instead.
const issuer = typeof window === "undefined" ? undefined : window.OIDC_ISSUER;
if (!issuer) {
  throw new Error(
    "OIDC_ISSUER is not set. Set it in the frontend container's environment (e.g. http://localhost:18081/realms/direkt) and restart it.",
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
