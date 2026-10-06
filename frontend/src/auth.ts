import { UserManager, WebStorageStateStore } from "oidc-client-ts";

import { oidcAuthority, oidcClientId, oidcRedirectUri } from "./oidcConfig";
import { ROUTES } from "./routes";

/** The single UserManager, so api.ts and the socket read the live token, silent renew included. */
export const userManager = new UserManager({
  authority: oidcAuthority,
  client_id: oidcClientId,
  redirect_uri: oidcRedirectUri,
  post_logout_redirect_uri: window.location.origin + "/",
  // Asked for, since the profile screen renders these claims.
  scope: "openid profile email",
  userStore: new WebStorageStateStore({ store: window.localStorage }),
});

export async function currentAccessToken(): Promise<string | null> {
  const user = await userManager.getUser();
  return user && !user.expired ? user.access_token : null;
}

// sessionStorage, not `user.state`, which survives in localStorage and would jump on every reload.
const RETURN_TO_KEY = "calltrainer.returnTo";

export function rememberReturnTo(path: string): void {
  if (path && path !== ROUTES.training) sessionStorage.setItem(RETURN_TO_KEY, path);
}

export function consumeReturnTo(): string | null {
  const path = sessionStorage.getItem(RETURN_TO_KEY);
  sessionStorage.removeItem(RETURN_TO_KEY);
  // Same-origin paths only: "//evil.example" is protocol-relative.
  return path && path.startsWith("/") && !path.startsWith("//") ? path : null;
}
