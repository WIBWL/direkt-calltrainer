import type { ReactNode } from "react";

/**
 * An "i" that folds a long explanation out of the way.
 *
 * The screens around consent and stored data have to *say* a lot — what is
 * kept, where it is processed, what a withdrawal destroys — but a wall of it is
 * read by nobody, and an unread notice informs no one. So the sentence a
 * decision actually turns on stays visible, and the background moves in here.
 *
 * A native `<details>`, not a state toggle: it is keyboard- and
 * screen-reader-operable without any work, it opens on in-page find, and it
 * prints expanded. The summary carries the whole accessible name, so the icon
 * itself is decorative.
 */
export default function InfoDetails({
  label = "Mehr dazu",
  children,
}: {
  label?: string;
  children: ReactNode;
}) {
  return (
    <details className="info-details">
      <summary className="info-summary">
        <span className="info-icon" aria-hidden="true">
          i
        </span>
        {label}
      </summary>

      <div className="info-body">{children}</div>
    </details>
  );
}
