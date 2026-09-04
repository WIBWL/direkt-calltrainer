/**
 * Joins class names, dropping the falsy ones, so a conditional modifier reads
 * as one argument instead of a string concatenation:
 * `cx("persona-card", isSelected && "selected")`.
 */
export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}
