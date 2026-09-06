import { useAuth } from "react-oidc-context";

/**
 * The signed-in user, as the interface needs them.
 *
 * Everything here comes out of the ID token — there is no account endpoint to
 * call, and deliberately so: identity lives in Keycloak and the app keeps no
 * User table of its own (ADR 0031). What the profile screen shows is therefore
 * exactly what the realm asserts, and none of it is the app's to edit.
 *
 * Every field is optional in OIDC and Keycloak only fills what the account has,
 * so each one degrades on its own rather than blanking the screen.
 */
export interface Account {
  /** Best available human name; falls back to the username, then to a label. */
  displayName: string;
  /** One or two letters for the avatar. Never empty. */
  initials: string;
  username: string | null;
  email: string | null;
  emailVerified: boolean;
}

const FALLBACK_NAME = "Angemeldet";

/** Up to two initials from a full name, or one from a single word. */
function initialsFrom(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const first = parts[0];
  if (!first) return "?";
  const last = parts.length > 1 ? parts[parts.length - 1] : undefined;
  // Taken per grapheme rather than per code unit, so a name starting with a
  // character outside the BMP does not lose half of itself.
  return [first, last]
    .filter((part): part is string => part !== undefined)
    .map((part) => [...part][0]?.toUpperCase() ?? "")
    .join("");
}


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
    // Initials come from the name, not from the fallback label: "AN" for
    // "Angemeldet" would look like a person's initials and be wrong.
    initials: asString(fullName) || username ? initialsFrom(displayName) : "?",
    username,
    email: asString(claims?.email),
    emailVerified: claims?.email_verified === true,
  };
}
