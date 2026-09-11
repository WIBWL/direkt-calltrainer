import type { ReactNode } from "react";

import { cx } from "../utils/cx";

/**
 * The heading of a section: eyebrow, title, and whatever belongs at its
 * right-hand end.
 *
 * It sits *above* the white box rather than inside it, and every section does
 * the same — which was the point of introducing it. Half of the feedback page's
 * sections used to carry their heading inside the box and half above it, so
 * two blocks of the same kind looked like two different kinds of thing.
 *
 * A box may still hold a title of its own, but only for an *item* inside a
 * section: the two offers under "Nächste Schritte" are each a thing you can
 * pick, not a section of the page.
 *
 * Its own module because two screens use it: the wrap-up and the progress
 * dashboard, which took the same headings so that the page reading many
 * trainings and the page reading one speak the same visual language.
 */
export default function SectionHeading({
  eyebrow,
  title,
  id,
  icon,
  aside,
  tone,
}: {
  eyebrow: string;
  title: string;
  /** For a section that names itself by its heading (`aria-labelledby`). */
  id?: string;
  /** The mark before the heading, where a section has one. */
  icon?: ReactNode;
  /** Kept at the far end of the row — a count, a control. */
  aside?: ReactNode;
  tone?: "success" | "danger";
}) {
  return (
    <div className={cx("feedback-section-head", tone && `is-${tone}`)}>
      {icon && (
        <div className="feedback-section-icon" aria-hidden="true">
          {icon}
        </div>
      )}

      <div className="feedback-section-heading">
        <div className="feedback-section-eyebrow">{eyebrow}</div>
        <h2 className="feedback-section-title" id={id}>
          {title}
        </h2>
      </div>

      {aside && <div className="feedback-section-aside">{aside}</div>}
    </div>
  );
}
