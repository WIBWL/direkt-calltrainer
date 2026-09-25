import type { ReactNode } from "react";

import { cx } from "../utils/cx";

/**
 * A section heading (title, optional right-hand content), always *above* the white box. A box holds a
 * title only for an item within a section. Shared by the wrap-up and the progress dashboard so both speak the
 * same visual language.
 */
export default function SectionHeading({
  title,
  id,
  aside,
  icon,
  tone,
}: {
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
        <h2 className="feedback-section-title" id={id}>
          {title}
        </h2>
      </div>

      {aside && <div className="feedback-section-aside">{aside}</div>}
    </div>
  );
}
