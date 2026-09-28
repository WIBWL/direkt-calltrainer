// OIDC configuration. The issuer comes at runtime (config.ts), under the
// backend's own name, so one image serves every realm. The client id is the
// same in every realm, so not a setting.
import { oidcIssuer } from "./config";

/** The realm issuer URL; the OIDC `authority`. Must match the backend's `iss` check. */
export const oidcAuthority: string = oidcIssuer;

/** The public Keycloak client that performs the login (see keycloak/direkt-realm.json). */
export const oidcClientId = "direkt-calltrainer";

/**
 * Where Keycloak sends the user back: always the SPA origin, so the realm needs
 * one redirect URI. Returning to the requested page is the app's job
 * (`onSigninCallback` in main.tsx).
 */
export const oidcRedirectUri: string =
  typeof window === "undefined" ? "" : window.location.origin + "/";
