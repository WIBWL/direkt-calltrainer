// OIDC configuration, read from build-time Vite env (repo-root .env, via
// vite.config's `envDir`). The reference project (direkt-dataplatform) serves
// this at runtime because it ships one image to many hosts; Calltrainer builds
// per deploy, so build-time — the same as VITE_API_URL — is enough.

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

export const oidcAuthority: string = issuer;
export const oidcClientId: string = import.meta.env.VITE_OIDC_CLIENT_ID ?? "calltrainer-frontend";
// The app has no router; the SPA origin is the redirect target and
// react-oidc-context strips the `?code=&state=` from the URL after the exchange.
export const oidcRedirectUri: string =
  typeof window === "undefined" ? "" : window.location.origin + "/";
