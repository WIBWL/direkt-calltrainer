import { useAuth } from "react-oidc-context";

import { initialsOf } from "../utils/initials";

/** From the ID token alone (ADR 0031); every claim is optional. */
export interface Account {
  displayName: string;
  /** Never empty. */
  initials: string;
  username: string | null;
  email: string | null;
  emailVerified: boolean;
}

const FALLBACK_NAME = "Angemeldet";

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim() !== "" ? value : null;
}

export function useAccount(): Account {
  const { user } = useAuth();
  const claims = user?.profile;

  const given = asString(claims?.given_name);
  const family = asString(claims?.family_name);
  const fullName = asString(claims?.name) ?? [given, family].filter(Boolean).join(" ");
  const username = asString(claims?.preferred_username);
  const displayName = asString(fullName) ?? username ?? FALLBACK_NAME;

  return {
    displayName,
    // Not from a generic fallback label, which would look like a person's.
    initials: (asString(fullName) || username ? initialsOf(displayName) : "") || "?",
    username,
    email: asString(claims?.email),
    emailVerified: claims?.email_verified === true,
  };
}
