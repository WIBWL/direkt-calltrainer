// OIDC configuration, read from build-time Vite env (repo-root .env, via
// vite.config's `envDir`). The reference project (direkt-dataplatform) serves
// this at runtime because it ships one image to many hosts; Calltrainer builds
// one image per deploy, so a build-time value is enough.

// Required, deliberately without a default: every candidate value is wrong in
// some environment, and getting it wrong does not fail at build — the app just
// mints tokens the backend rejects, surfacing as a 401 far from the cause. Fail
// loudly instead.
const issuer = import.meta.env.VITE_OIDC_ISSUER;
if (!issuer) {
  throw new Error(
    "VITE_OIDC_ISSUER is not set. Add it to .env (e.g. http://localhost:18081/realms/direkt) and rebuild.",
  );
}

/** The realm issuer URL; the OIDC `authority`. Must match the backend's `iss` check. */
export const oidcAuthority: string = issuer;

/** The public Keycloak client that performs the login (see keycloak/direkt-realm.json). */
export const oidcClientId: string = import.meta.env.VITE_OIDC_CLIENT_ID ?? "calltrainer-frontend";

/**
 * Where Keycloak sends the user back. The app has no router, so the SPA origin
 * is the target and react-oidc-context strips the `?code=&state=` after the
 * exchange.
 */
export const oidcRedirectUri: string =
  typeof window === "undefined" ? "" : window.location.origin + "/";
