import type { ReactNode } from "react";

import { cx } from "../utils/cx";

/** Always above the white box; shared by the wrap-up and the dashboard. */
export default function SectionHeading({
  title,
  id,
  aside,
  icon,
  tone,
}: {
  title: string;
  id?: string;
  icon?: ReactNode;
  /** At the far end of the row. */
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
