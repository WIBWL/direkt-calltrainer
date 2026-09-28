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
async function reauthenticate(): Promise<void> {
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
 * The one place a request is authorised; raw response (`apiFetch` for JSON).
 * The token is read from the live OIDC session at call time (auth.ts). A 401
 * triggers a re-login redirect; any other non-2xx throws an `ApiError`.
 */
export async function authorizedFetch(path: string, init?: RequestInit): Promise<Response> {
  const token = await currentAccessToken();
  if (!token) {
    void reauthenticate();
    throw new ApiError(401, "no active session");
  }
  const response = await fetch(path, {
    ...init,
    headers: {
      // Only a string body is JSON here: a FormData body has to set its own
      // multipart content type, boundary included.
      ...(typeof init?.body === "string" ? { "Content-Type": "application/json" } : {}),
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
  return response;
}

/** Authenticated JSON request (see `authorizedFetch`). */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await authorizedFetch(path, init);
  return (response.status === 204 ? null : await response.json()) as T;
}

