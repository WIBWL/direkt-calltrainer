/**
 * Up to two initials for an avatar: the first letter of the first and of the
 * last part of a name, so "Anna Maria Berger" reads "AB".
 *
 * One function for every avatar in the app — the account chip, a Persona's
 * portrait fallback and the transcript's speaker marks — so the same name
 * cannot come out as two different pairs of letters on two screens.
 *
 * Taken per grapheme rather than per code unit, so a name starting with a
 * character outside the BMP does not lose half of itself. Empty for an empty
 * name; what stands in for it is the caller's to decide.
 */
export function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const first = parts[0];
  if (!first) return "";
  const last = parts.length > 1 ? parts[parts.length - 1] : undefined;
  return [first, last]
    .filter((part): part is string => part !== undefined)
    .map((part) => [...part][0]?.toUpperCase() ?? "")
    .join("");
}
