import { currentAccessToken } from "./auth";

/** A non-2xx reply from the backend. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, detail?: string) {
    super(detail ? `Request failed: ${status} — ${detail}` : `Request failed: ${status}`);
    this.status = status;
  }
}

/**
 * Authenticated JSON request. `path` is a same-origin absolute path ("/api/…"):
 * the backend serves this SPA, so there is no separate API host (see CLAUDE.md).
 * The bearer token is read from the live OIDC session at call time (see auth.ts),
 * so a rotated token is picked up automatically and callers never pass one.
 * Mirrors direkt-dataplatform's api.ts.
 */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = await currentAccessToken();
  if (!token) {
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
  if (!response.ok) {
    const body = (await response.json().catch(() => undefined)) as { detail?: unknown } | undefined;
    throw new ApiError(response.status, typeof body?.detail === "string" ? body.detail : undefined);
  }
  return (response.status === 204 ? null : await response.json()) as T;
}
