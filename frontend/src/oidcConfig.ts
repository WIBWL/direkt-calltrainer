// The issuer comes at runtime (config.ts); the client id is the same in every realm.
import { oidcIssuer } from "./config";

/** Must match the backend's `iss` check. */
export const oidcAuthority: string = oidcIssuer;

/** keycloak/direkt-realm.json. */
export const oidcClientId = "calltrainer-frontend";

/** Always the SPA origin, so the realm needs one redirect URI; main.tsx returns to the page. */
export const oidcRedirectUri: string =
  typeof window === "undefined" ? "" : window.location.origin + "/";
