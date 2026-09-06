import { currentAccessToken, userManager } from "./auth";

/** A non-2xx reply from the backend. */
export class ApiError extends Error {
  readonly status: number;
  /** The backend's `detail` string, when it sent one — safe to show the user. */
  readonly detail?: string;

  constructor(status: number, detail?: string) {
    super(detail ? `Request failed: ${status} — ${detail}` : `Request failed: ${status}`);
    this.status = status;
    if (detail !== undefined) this.detail = detail;
  }
}

// Set once we have started a re-login redirect, so a burst of parallel requests
// (the setup screen fires several on mount) does not each kick one off.
let reauthStarted = false;

/** The stored session looks valid locally but the server rejected the token —
 * a stale signing key after the Keycloak realm was re-imported, a revoked
 * session, a wiped realm. Drop the local user and send the browser back through
 * login; on return the original page is restored. */
export async function reauthenticate(): Promise<void> {
  if (reauthStarted) return;
  reauthStarted = true;
  try {
    await userManager.removeUser();
  } catch {
    // best effort — the redirect below is what matters
  }
  void userManager.signinRedirect({
    state: { returnTo: window.location.pathname + window.location.search },
  });
}

/**
 * Authenticated JSON request. `path` is a same-origin absolute path ("/api/…"):
 * the backend serves this SPA, so there is no separate API host (see CLAUDE.md).
 * The bearer token is read from the live OIDC session at call time (see auth.ts),
 * so a rotated token is picked up automatically and callers never pass one.
 * A server 401 (we had a token, it was rejected) triggers a re-login redirect.
 * Mirrors direkt-dataplatform's api.ts.
 */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = await currentAccessToken();
  if (!token) {
    void reauthenticate();
    throw new ApiError(401, "no active session");
  }
  const response = await fetch(path, {
    ...init,
    headers: {
      ...(init?.body === undefined ? {} : { "Content-Type": "application/json" }),
      Authorization: `Bearer ${token}`,
      ...init?.headers,
    },
  });
  if (response.status === 401) {
    void reauthenticate();
    throw new ApiError(401, "session invalid — re-authenticating");
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => undefined)) as { detail?: unknown } | undefined;
    throw new ApiError(response.status, typeof body?.detail === "string" ? body.detail : undefined);
  }
  return (response.status === 204 ? null : await response.json()) as T;
}
