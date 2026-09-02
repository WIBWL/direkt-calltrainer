import { UserManager, WebStorageStateStore } from "oidc-client-ts";

import { oidcAuthority, oidcClientId, oidcRedirectUri } from "./oidcConfig";

/**
 * The app's single UserManager and the source of truth for the access token.
 *
 * Constructed here (not by react-oidc-context from settings) so api.ts and
 * useSessionSocket.ts can read the live token at request time
 * (`userManager.getUser()`) rather than a copy captured during render — silent
 * renew is then picked up automatically. Mirrors direkt-dataplatform's auth.ts.
 */
export const userManager = new UserManager({
  authority: oidcAuthority,
  client_id: oidcClientId,
  redirect_uri: oidcRedirectUri,
  post_logout_redirect_uri: window.location.origin + "/",
  userStore: new WebStorageStateStore({ store: window.localStorage }),
});

/** The current access token, or null if there is no valid session. */
export async function currentAccessToken(): Promise<string | null> {
  const user = await userManager.getUser();
  return user && !user.expired ? user.access_token : null;
}
