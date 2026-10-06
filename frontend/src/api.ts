import { currentAccessToken, userManager } from "./auth";
import { apiUrl } from "./config";

export class ApiError extends Error {
  readonly status: number;
  /** Safe to show the user. */
  readonly detail?: string;

  constructor(status: number, detail?: string) {
    super(detail ? `Request failed: ${status} — ${detail}` : `Request failed: ${status}`);
    this.status = status;
    if (detail !== undefined) this.detail = detail;
  }
}

// So parallel requests do not each start a redirect.
let reauthStarted = false;

/** A locally valid session the server rejected (e.g. after a realm re-import): log in again. */
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

/** The one place a request is authorised, with the live token (auth.ts). 401
 * re-logs in; any other non-2xx throws `ApiError`. */
export async function authorizedFetch(path: string, init?: RequestInit): Promise<Response> {
  const token = await currentAccessToken();
  if (!token) {
    void reauthenticate();
    throw new ApiError(401, "no active session");
  }
  const response = await fetch(apiUrl + path, {
    ...init,
    headers: {
      // FormData sets its own multipart content type.
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

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await authorizedFetch(path, init);
  return (response.status === 204 ? null : await response.json()) as T;
}

