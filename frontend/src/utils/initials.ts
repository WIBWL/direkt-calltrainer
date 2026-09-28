/**
 * Up to two initials ("Anna Maria Berger" → "AB") for every avatar in the app.
 * Taken per grapheme, not code unit, so a non-BMP first character stays whole.
 * Empty for an empty name; the fallback is the caller's.
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
