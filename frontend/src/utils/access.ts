/**
 * Whether the logged-in User may use the Calltrainer at all (ADR 0109): the
 * access token has to carry the client role `calltrainer-user`, which the
 * backend checks on every request and on the call's socket. Read here only to
 * show a screen that says so, instead of one failed request after another;
 * the backend's check is the one that counts.
 */

/** The client role that admits a User — `REQUIRED_ROLE` in backend/auth.py. */
export const REQUIRED_ROLE = "calltrainer-user";

/** The payload of a JWT, or null for anything that is not one. Not verified:
 * the token came from our own login, and nothing here grants anything. */
function payloadOf(token: string): unknown {
  const part = token.split(".")[1];
  if (!part) return null;
  try {
    const base64 = part.replace(/-/g, "+").replace(/_/g, "/");
    const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
    return JSON.parse(new TextDecoder().decode(bytes));
  } catch {
    return null;
  }
}

/** True when `accessToken` carries `REQUIRED_ROLE` as a role of `clientId`
 * (`resource_access.<client>.roles`, where Keycloak puts client roles). */
export function holdsRequiredRole(accessToken: string, clientId: string): boolean {
  const payload = payloadOf(accessToken) as
    | { resource_access?: Record<string, { roles?: unknown }> }
    | null;
  const roles = payload?.resource_access?.[clientId]?.roles;
  return Array.isArray(roles) && roles.includes(REQUIRED_ROLE);
}
