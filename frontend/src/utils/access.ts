/** The role gate (ADR 0109), read here only to show a screen; the backend's check is the one that counts. */

/** `REQUIRED_ROLE` in backend/auth.py. */
export const REQUIRED_ROLE = "calltrainer-user";

/** Not verified: nothing here grants anything. */
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

/** Keycloak puts client roles under `resource_access.<client>.roles`. */
export function holdsRequiredRole(accessToken: string, clientId: string): boolean {
  const payload = payloadOf(accessToken) as
    | { resource_access?: Record<string, { roles?: unknown }> }
    | null;
  const roles = payload?.resource_access?.[clientId]?.roles;
  return Array.isArray(roles) && roles.includes(REQUIRED_ROLE);
}
