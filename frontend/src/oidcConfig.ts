// OIDC configuration. The issuer is read from build-time Vite env (repo-root
// .env, via vite.config's `envDir`), under the backend's own name rather than a
// VITE_-prefixed copy: it is the same value the backend checks `iss` against,
// and two copies of it in .env under two names is a pair that can disagree, so
// vite.config widens `envPrefix` to let the SPA read it. The client id is not a
// setting at all -- it is the same in every realm.
//
// A one-image-many-hosts deployment would need this resolved at runtime
// instead; Calltrainer builds one image per deploy, so a build-time value is
// enough.

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
 * Where Keycloak sends the user back: always the SPA origin, never the page the
 * user was on. Keeping it to one URL means the realm needs one registered
 * redirect URI no matter how many routes the app grows.
 *
 * Getting back to the requested page is therefore the app's job, not Keycloak's
 * — `onSigninCallback` in main.tsx strips the `?code=&state=` and hands the
 * stored path to the router, which has to perform the navigation itself
 * (`history.replaceState` fires no event the router would hear).
 */
export const oidcRedirectUri: string =
  typeof window === "undefined" ? "" : window.location.origin + "/";
