import { UserManager, WebStorageStateStore } from "oidc-client-ts";

import { oidcAuthority, oidcClientId, oidcRedirectUri } from "./oidcConfig";
import { ROUTES } from "./routes";

/**
 * The app's single UserManager and the source of truth for the access token.
 *
 * Constructed here (not by react-oidc-context from settings) so api.ts and
 * useSessionSocket.ts can read the live token at request time
 * (`userManager.getUser()`) rather than a copy captured during render — silent
 * renew is then picked up automatically.
 */
export const userManager = new UserManager({
  authority: oidcAuthority,
  client_id: oidcClientId,
  redirect_uri: oidcRedirectUri,
  post_logout_redirect_uri: window.location.origin + "/",
  // Stated rather than left to the default ("openid"), because the profile
  // screen renders these claims: the realm assigns `profile` and `email` as
  // default client scopes, so Keycloak would include them either way — but
  // that is the realm's choice, and a screen that depends on a claim should
  // ask for it rather than rely on a server-side default staying put.
  scope: "openid profile email",
  userStore: new WebStorageStateStore({ store: window.localStorage }),
});

/** The current access token, or null if there is no valid session. */
export async function currentAccessToken(): Promise<string | null> {
  const user = await userManager.getUser();
  return user && !user.expired ? user.access_token : null;
}

// Where to go once the login redirect has been processed. Kept in
// sessionStorage rather than read back off the OIDC user: `user.state`
// survives in localStorage and would re-trigger the same jump on every later
// reload, whereas this is consumed exactly once, by the tab that logged in.
const RETURN_TO_KEY = "calltrainer.returnTo";

/** Remember the path the user asked for before being sent to Keycloak. */
export function rememberReturnTo(path: string): void {
  // "/" is where the redirect lands anyway; storing it would only cause a
  // redundant navigation.
  if (path && path !== ROUTES.training) sessionStorage.setItem(RETURN_TO_KEY, path);
}

/** The remembered path, removed as it is read. Null when there is none. */
export function consumeReturnTo(): string | null {
  const path = sessionStorage.getItem(RETURN_TO_KEY);
  sessionStorage.removeItem(RETURN_TO_KEY);
  // Same-origin paths only. The value is ours, but it ends up in a navigation,
  // and "//evil.example" is a protocol-relative URL rather than a path.
  return path && path.startsWith("/") && !path.startsWith("//") ? path : null;
}
