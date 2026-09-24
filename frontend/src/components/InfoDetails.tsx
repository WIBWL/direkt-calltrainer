import type { ReactNode } from "react";

/**
 * An "i" that folds a long explanation away, keeping the deciding sentence visible.
 * A native `<details>`: keyboard/screen-reader operable, opens on find, prints expanded.
 * The summary carries the accessible name; `iconOnly` hides it from the eye only.
 */
export default function InfoDetails({
  label = "Mehr dazu",
  iconOnly = false,
  children,
}: {
  label?: string;
  iconOnly?: boolean;
  children: ReactNode;
}) {
  return (
    <details className={"info-details" + (iconOnly ? " info-details-icon" : "")}>
      <summary className="info-summary">
        <span className="info-icon" aria-hidden="true">
          i
        </span>
        {iconOnly ? <span className="visually-hidden">{label}</span> : label}
      </summary>

      <div className="info-body">{children}</div>
    </details>
  );
}
