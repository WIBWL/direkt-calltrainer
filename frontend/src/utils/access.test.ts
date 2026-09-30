import { describe, expect, it } from "vitest";

import { REQUIRED_ROLE, holdsRequiredRole } from "./access";

/** The SPA's reading of the role gate (ADR 0109). A wrong answer either locks
 * an admitted User out of the app or shows an outsider a screen whose every
 * request then fails — so both directions are pinned. */

const CLIENT = "direkt-calltrainer";

/** An unsigned JWT with `payload`; nothing here checks the signature. */
function token(payload: object): string {
  const encode = (value: object) =>
    btoa(String.fromCharCode(...new TextEncoder().encode(JSON.stringify(value))))
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/, "");
  return `${encode({ alg: "RS256" })}.${encode(payload)}.signature`;
}

describe("holdsRequiredRole", () => {
  it("admits a token carrying the client role", () => {
    const t = token({ resource_access: { [CLIENT]: { roles: ["x", REQUIRED_ROLE] } } });
    expect(holdsRequiredRole(t, CLIENT)).toBe(true);
  });

  it("refuses a token without it", () => {
    expect(holdsRequiredRole(token({}), CLIENT)).toBe(false);
    expect(holdsRequiredRole(token({ resource_access: { [CLIENT]: { roles: [] } } }), CLIENT)).toBe(false);
  });

  it("refuses the same name as another client's or a realm role", () => {
    // In a realm shared with other services, either is somebody else's to hand out.
    expect(
      holdsRequiredRole(token({ resource_access: { other: { roles: [REQUIRED_ROLE] } } }), CLIENT),
    ).toBe(false);
    expect(holdsRequiredRole(token({ realm_access: { roles: [REQUIRED_ROLE] } }), CLIENT)).toBe(false);
  });

  it("reads a payload whose claims are not ASCII", () => {
    const t = token({
      name: "Jürgen Müller",
      resource_access: { [CLIENT]: { roles: [REQUIRED_ROLE] } },
    });
    expect(holdsRequiredRole(t, CLIENT)).toBe(true);
  });

  it("answers false, not a crash, for something that is not a JWT", () => {
    expect(holdsRequiredRole("", CLIENT)).toBe(false);
    expect(holdsRequiredRole("not-a-jwt", CLIENT)).toBe(false);
    expect(holdsRequiredRole("a.%%%.c", CLIENT)).toBe(false);
  });
});
